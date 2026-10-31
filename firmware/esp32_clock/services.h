// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <Preferences.h>
#include <FlipCalendar.h>
#include <FlipStorage.h>
namespace clockapp {
using namespace flip;
class Rtc {
 public:
  int64_t utc=0;
  bool valid=false;
  uint32_t lastGood=0,errors=0;
  bool pcf8563() const { return pcf_; }
  bool read(uint32_t now) {
    uint8_t b[7],status;
    if(!locate() || !readTime(b,status)) { ++errors; ++failures_; found_=false; }
    else {
      int64_t v=decodeRtc(b,status);
      if(validUtc(v)) { utc=v; valid=true; failures_=0; lastGood=now; return true; }
      valid=false; ++failures_;
    }
    if(failures_>=3 || uint32_t(now-lastGood)>3000) valid=false;
    return false;
  }
  bool write(int64_t value,uint32_t now) {
    uint16_t y; uint8_t m,d,h,n,s;
    if(!utcCalendar(value,y,m,d,h,n,s)) return false;
    if(!locate()) return valid=false;
    uint8_t check[7],status;
    if(pcf_) {
      // PCF8563: registers 0x02..0x08 (VL is bit 7 of seconds, cleared by this write); weekday is 0..6.
      uint8_t control[2]={0,0}; // run, no test mode, alarms/timer/interrupt disabled
      uint8_t p[7]={bcd(s),bcd(n),bcd(h),bcd(d),uint8_t((value/86400+4)%7),bcd(m),bcd(uint8_t(y-2000))};
      if(!writeReg(0x00,control,2) || !writeReg(0x02,p,7) || !readTime(check,status)) return valid=false;
      int64_t got=decodeRtc(check,status);
      if(got<value || got>value+1) return valid=false;
      return read(now) && utc>=value && utc<=value+2;
    }
    uint8_t b[7]={bcd(s),bcd(n),bcd(h),uint8_t((value/86400+4)%7+1),bcd(d),bcd(m),bcd(uint8_t(y-2000))};
    // Clear OSF only after the written calendar registers have been read back.
    if(!writeReg(0,b,7)) return valid=false;
    if(!readTime(check,status)) return valid=false;
    int64_t got=decodeRtc(check,uint8_t(status&0x7f));
    if(got<value || got>value+1) return valid=false;
    status&=0x7f;
    if(!writeReg(0x0f,&status,1)) return valid=false;
    return read(now) && utc>=value && utc<=value+2;
  }
 private:
  uint8_t failures_=0,addr_=0x68; bool found_=false,pcf_=false;
  // DS3231 at 0x68 is preferred; PCF8563 modules (e.g. HW-689) answer at 0x51.
  bool locate() {
    if(found_) return true;
    for(uint8_t candidate:{uint8_t(0x68),uint8_t(0x51)}) {
      Wire.beginTransmission(candidate);
      if(Wire.endTransmission()==0) { addr_=candidate; pcf_=candidate==0x51; found_=true; return true; }
    }
    return false;
  }
  // Both chips are normalised to the DS3231 register layout that decodeRtc() understands.
  bool readTime(uint8_t* b,uint8_t& status) {
    if(!pcf_) return readReg(0,b,7) && readReg(0x0f,&status,1);
    uint8_t p[7];
    if(!readReg(0x02,p,7)) return false;
    status=(p[0]&0x80)?0x80:0; // VL: clock integrity not guaranteed
    b[0]=p[0]&0x7f; b[1]=p[1]&0x7f; b[2]=p[2]&0x3f; b[3]=uint8_t((p[4]&7)+1); b[4]=p[3]&0x3f;
    b[5]=p[5]&0x9f; b[6]=p[6]; // century bit kept so a non-2000s date is rejected
    return true;
  }
  bool readReg(uint8_t reg,uint8_t* data,uint8_t n) {
    Wire.beginTransmission(addr_); Wire.write(reg);
    if(Wire.endTransmission(false)!=0 || Wire.requestFrom(addr_,n)!=n) return false;
    for(uint8_t i=0;i<n;++i) data[i]=uint8_t(Wire.read()); return true;
  }
  bool writeReg(uint8_t reg,const uint8_t* data,uint8_t n) {
    Wire.beginTransmission(addr_); Wire.write(reg); Wire.write(data,n); return Wire.endTransmission()==0;
  }
};
class Store {
 public:
  Saved saved;
  bool ready=false,dirty=false,fault=false,throttled=false;
  uint32_t writes=0,lastWrite=0;
  bool begin(Config& config) {
    ready=prefs.begin("flip-clock",false); if(!ready) { fault=true; return false; }
    uint8_t a[BLOB_SIZE]={},b[BLOB_SIZE]={};
    size_t an=prefs.getBytesLength("a"),bn=prefs.getBytesLength("b");
    if(an==BLOB_SIZE) prefs.getBytes("a",a,BLOB_SIZE);
    if(bn==BLOB_SIZE) prefs.getBytes("b",b,BLOB_SIZE);
    slot_=selectSlot(a,an==BLOB_SIZE?an:0,b,bn==BLOB_SIZE?bn:0,saved);
    if(slot_>=0) { config=saved.config; return true; }
    dirty=true;
    // Empty NVS is commissioning. Nonempty unreadable/unknown schema requires service.
    fault=an!=0 || bn!=0; return !fault;
  }
  bool save(const Planner& p,const Rtc& rtc,uint8_t phase,uint32_t now) {
    throttled=false;
    if(!ready || fault || saved.generation==0xffffffffUL) return false;
    Saved next=saved; next.config=p.config; next.generation=saved.generation+1;
    uint8_t before[BLOB_SIZE],withConfig[BLOB_SIZE];
    encodeSaved(saved,before); Saved configured=saved; configured.config=p.config; encodeSaved(configured,withConfig);
    bool configChanged=memcmp(before,withConfig,BLOB_SIZE)!=0;
    if(p.position && rtc.valid && (!saved.hasSnapshot || saved.display!=p.display || saved.r!=p.remainder || saved.phase!=phase || configChanged)) {
      next.hasSnapshot=true; next.display=p.display; next.r=p.remainder; next.utc=rtc.utc; next.phase=phase;
      next.snapshotGeneration=next.generation; next.source=p.committed?2:1; next.snapshotCycle=p.config.cycle;
    }
    uint8_t old[BLOB_SIZE],data[BLOB_SIZE],check[BLOB_SIZE];
    encodeSaved(next,data); Saved same=next; same.generation=saved.generation; encodeSaved(same,old);
    uint8_t prior[BLOB_SIZE]; encodeSaved(saved,prior);
    if(slot_>=0 && !memcmp(old,prior,BLOB_SIZE)) { dirty=false; return true; }
    if(writes && uint32_t(now-lastWrite)<5000) { throttled=true; return false; }
    const char* key=slot_==0?"b":"a";
    Saved verified;
    if(prefs.putBytes(key,data,BLOB_SIZE)!=BLOB_SIZE || prefs.getBytes(key,check,BLOB_SIZE)!=BLOB_SIZE || memcmp(data,check,BLOB_SIZE) || !decodeSaved(check,BLOB_SIZE,verified)) {
      fault=true; return false;
    }
    slot_=slot_==0?1:0; saved=next; dirty=false; ++writes; lastWrite=now; return true;
  }
  // Explicit local service command only; RTC and BLE bond partition are untouched.
  bool resetConfig() {
    prefs.remove("a"); prefs.remove("b");
    if(prefs.getBytesLength("a") || prefs.getBytesLength("b")) return false;
    fault=false; slot_=-1; saved=Saved(); dirty=true; return true;
  }
 private:
  Preferences prefs; int slot_=-1;
};
class Link {
 public:
  Frame status;
  uint32_t session=0,seq=0,errors=0,lastRead=0;
  bool online=false,ready=false,pending=false,fault=false;
  uint8_t result=0;
  uint32_t acknowledged=0;
  void begin() { do { session=esp_random(); } while(!session); }
  bool running() const { return online && status.op()==RUNNING; }
  bool armed() const { return online && (status.bytes[3]&2); }
  bool coilZero() const { return online && (status.bytes[3]&8); }
  bool send(Op op,uint32_t a=0,uint32_t b=0,uint32_t c=0,uint32_t d=0) {
    if(pending || !ready || fault || seq>=0xfffffffeUL) return false;
    waiting_=command(op,session,++seq); waiting_.arg(0,a); waiting_.arg(1,b); waiting_.arg(2,c); waiting_.arg(3,d); waiting_.seal();
    pending=true; attempts_=0; sent_=millis(); transmit(waiting_); return true;
  }
  bool stop() {
    // STOP supersedes a pending application request; position must be invalidated by caller.
    pending=false;
    if(!online || status.session()!=session || seq>=0xfffffffeUL) return false;
    ready=true; fault=false; return send(STOP);
  }
  void tick(uint32_t now) {
    if(fault) return; // Do not refresh lease after an uncertain transaction.
    if(uint32_t(now-lastPoll_)>=50) {
      lastPoll_=now;
      Frame f; uint8_t n=Wire.requestFrom(uint8_t(0x12),uint8_t(32));
      if(n==32) { for(uint8_t i=0;i<32;++i) f.bytes[i]=uint8_t(Wire.read()); }
      if(n!=32 || !f.valid() || f.op()>FAULT || (f.bytes[3]&0xf0)) { ++errors; }
      else {
        bool wasReady=ready; status=f; online=true; lastRead=now;
        if(f.session()!=session) {
          ready=false;
          if(wasReady || pending) { fault=true; pending=false; return; }
          if(!(f.bytes[3]&2) && f.op()!=RUNNING && uint32_t(now-lastOpen_)>=200) {
            Frame open=command(OPEN,session); open.seal(); transmit(open); lastOpen_=now;
          }
        } else {
          ready=true;
          if(!wasReady) lastBeat_=now-250;
          if(pending && f.arg(2)==waiting_.seq()) {
            acknowledged=waiting_.seq(); result=uint8_t(get16(f.bytes+28)); pending=false;
          }
        }
      }
    }
    if(online && uint32_t(now-lastRead)>500) { online=false; ready=false; fault=true; pending=false; return; }
    if(ready && uint32_t(now-lastBeat_)>=250) {
      Frame beat=command(HEARTBEAT,session); beat.seal(); transmit(beat); lastBeat_=now;
    }
    if(pending && uint32_t(now-sent_)>=200) {
      if(attempts_>=3) { fault=true; pending=false; return; }
      ++attempts_; sent_=now; transmit(waiting_);
    }
    if(seq>=0xfffffffeUL && !pending && !running()) {
      // No wrap. Disarm in old generation before opening a fresh session.
      if(armed()) {
        waiting_=command(DISARM,session,0xffffffffUL); waiting_.seal(); transmit(waiting_);
      } else { begin(); seq=0; ready=false; acknowledged=0; }
    }
  }
  void retry() { fault=false; online=false; ready=false; pending=false; begin(); seq=0; lastPoll_=millis(); }
 private:
  Frame waiting_;
  uint32_t lastPoll_=0,lastBeat_=0,lastOpen_=0,sent_=0;
  uint8_t attempts_=0;
  void transmit(const Frame& f) {
    Wire.beginTransmission(0x12); Wire.write(f.bytes,32); if(Wire.endTransmission()!=0) ++errors;
  }
};
} // namespace clockapp
