#pragma once
#include "Arduino.h"
struct FakeWire {
  bool rtcMissing=false,unoMissing=false,dropMoveReply=false,failWrites=false,pcf=false; // pcf: a PCF8563 at 0x51 instead of DS3231 at 0x68
  uint32_t moveAccepts=0; int64_t rtcBase=1793462400LL; uint32_t rtcAt=0;
  uint8_t regs[32]={}; std::vector<uint8_t> tx,rx; uint8_t address=0,reg=0; size_t cursor=0;
  void begin(int,int,int) {} void setTimeOut(int) {}
  void beginTransmission(uint8_t addr) { address=addr; tx.clear(); }
  size_t write(uint8_t b) { tx.push_back(b); return 1; }
  size_t write(const uint8_t* b,size_t n) { tx.insert(tx.end(),b,b+n); return n; }
  uint8_t endTransmission(bool=true) {
    if(failWrites) return 4;
    if(address==0x12) {
      if(unoMissing) return 2;
      if(tx.size()==32) {
        flip::Frame f; memcpy(f.bytes,tx.data(),32); uint32_t prior=fakeUno.job;
        fakeUno.handle(f,fakeMs); if(f.op()==flip::MOVE && fakeUno.job!=prior) ++moveAccepts;
      }
    } else if(address==0x51) {
      if(rtcMissing || !pcf) return 2;
      if(!tx.empty()) reg=tx[0];
      for(size_t i=1;i<tx.size();++i) regs[reg+i-1]=tx[i];
      if(reg==2 && tx.size()==8) {
        uint8_t ds[7]={uint8_t(regs[2]&0x7f),uint8_t(regs[3]&0x7f),uint8_t(regs[4]&0x3f),uint8_t((regs[6]&7)+1),uint8_t(regs[5]&0x3f),uint8_t(regs[7]&0x9f),regs[8]};
        rtcBase=flip::decodeRtc(ds,(regs[2]&0x80)?0x80:0); rtcAt=fakeMs;
      }
    } else if(address==0x68) {
      if(rtcMissing || pcf) return 2;
      if(!tx.empty()) reg=tx[0];
      for(size_t i=1;i<tx.size();++i) regs[reg+i-1]=tx[i];
      if(reg==0 && tx.size()==8) { rtcBase=flip::decodeRtc(regs,0); rtcAt=fakeMs; }
    }
    return 0;
  }
  uint8_t requestFrom(uint8_t addr,uint8_t n) {
    rx.clear(); cursor=0;
    if(addr==0x12 && !unoMissing) {
      if(dropMoveReply && fakeUno.job && fakeUno.state==flip::DONE) return 0;
      auto f=fakeUno.status(fakeMs); rx.assign(f.bytes,f.bytes+32);
    } else if(addr==0x51 && pcf && !rtcMissing) {
      uint16_t y; uint8_t m,d,h,min,s; int64_t value=rtcBase+uint32_t(fakeMs-rtcAt)/1000;
      if(flip::utcCalendar(value,y,m,d,h,min,s)) {
        regs[2]=flip::bcd(s); regs[3]=flip::bcd(min); regs[4]=flip::bcd(h); regs[5]=flip::bcd(d);
        regs[6]=uint8_t((value/86400+4)%7); regs[7]=flip::bcd(m); regs[8]=flip::bcd(uint8_t(y-2000));
      }
      rx.assign(regs+reg,regs+reg+n);
    } else if(addr==0x68 && !rtcMissing && !pcf) {
      uint16_t y; uint8_t m,d,h,min,s;
      int64_t value=rtcBase+uint32_t(fakeMs-rtcAt)/1000;
      if(flip::utcCalendar(value,y,m,d,h,min,s)) {
        regs[0]=flip::bcd(s); regs[1]=flip::bcd(min); regs[2]=flip::bcd(h); regs[3]=1;
        regs[4]=flip::bcd(d); regs[5]=flip::bcd(m); regs[6]=flip::bcd(uint8_t(y-2000));
      }
      rx.assign(regs+reg,regs+reg+n);
    }
    return uint8_t(rx.size());
  }
  int read() { return cursor<rx.size()?rx[cursor++]:-1; }
}; inline FakeWire Wire;
