// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <Arduino.h>
#include <esp_timer.h>
#include <Preferences.h>
#include <FlipCalendar.h>
#include <FlipStorage.h>
namespace clockapp {
using namespace flip;
// No battery-backed RTC: time comes from SNTP over Wi-Fi (or, temporarily, from the phone) and is then kept by the
// ESP32 crystal. `valid` stays false after every power-up until the first network time arrives.
class NetClock {
 public:
  int64_t utc=0;
  bool valid=false;
  uint32_t lastGood=0,errors=0;
  bool read(uint32_t now) {
    if(!valid) return false;
    uint32_t whole=uint32_t(now-anchorMs_)/1000; // re-anchored on every call, so millis() wrap-around is harmless
    anchorUtc_+=whole; anchorMs_+=whole*1000; utc=anchorUtc_; lastGood=now; return true;
  }
  bool write(int64_t value,uint32_t now) {
    if(!validUtc(value)) return false;
    anchorUtc_=utc=value; anchorMs_=now; valid=true; lastGood=now; return true;
  }
 private:
  int64_t anchorUtc_=0; uint32_t anchorMs_=0;
};class Store {
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
  bool save(const Planner& p,const NetClock& rtc,uint8_t phase,uint32_t now) {
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
  // Explicit local service command only; the BLE bond partition is untouched.
  bool resetConfig() {
    prefs.remove("a"); prefs.remove("b");
    if(prefs.getBytesLength("a") || prefs.getBytesLength("b")) return false;
    fault=false; slot_=-1; saved=Saved(); dirty=true; return true;
  }
 private:
  Preferences prefs; int slot_=-1;
};
// Drives the ULN2003 from esp_timer's task, so web, Wi-Fi and BLE work in the loop cannot stall a move. A late
// step only pauses the motor: there is no catch-up burst. Every move is bounded, so coils always end up off.
class Motor {
 public:
  Motion m;
  void begin() {
    for(uint8_t pin:PINS) { pinMode(pin,OUTPUT); digitalWrite(pin,LOW); }
    esp_timer_create_args_t args={}; args.callback=&Motor::onTimer; args.arg=this; args.name="flip-step";
    esp_timer_create(&args,&timer_);
  }
  bool start(uint32_t steps,uint16_t rate,uint16_t accel,uint32_t timeoutMs,uint32_t nowMs) {
    esp_timer_stop(timer_);
    portENTER_CRITICAL(&mux_); bool ok=m.start(steps,rate,accel,timeoutMs,nowMs); portEXIT_CRITICAL(&mux_);
    if(!ok) return false;
    if(esp_timer_start_once(timer_,1)!=ESP_OK) { stop(); return false; }
    return true;
  }
  void stop() { esp_timer_stop(timer_); portENTER_CRITICAL(&mux_); m.stop(); write(); portEXIT_CRITICAL(&mux_); }
  void fail() { esp_timer_stop(timer_); portENTER_CRITICAL(&mux_); m.fail(); write(); portEXIT_CRITICAL(&mux_); }
  void clear() { esp_timer_stop(timer_); portENTER_CRITICAL(&mux_); m.clear(); write(); portEXIT_CRITICAL(&mux_); }
  void tick(uint32_t now) { if(m.timedOut(now)) fail(); }
  bool running() const { return m.state==Motion::RUNNING; }
  bool done() const { return m.state==Motion::DONE; }
  bool faulted() const { return m.state==Motion::FAULT; }
  bool coilZero() const { return m.mask==0; }
 private:
  static constexpr uint8_t PINS[4]={12,13,14,15}; // IN1..IN4; the only free pins with camera and SD unused
  esp_timer_handle_t timer_=nullptr;
  portMUX_TYPE mux_=portMUX_INITIALIZER_UNLOCKED;
  void write() { for(uint8_t i=0;i<4;++i) digitalWrite(PINS[i],(m.mask>>i)&1?HIGH:LOW); }
  static void onTimer(void* self) {
    Motor* motor=static_cast<Motor*>(self);
    portENTER_CRITICAL(&motor->mux_); uint32_t wait=motor->m.step(); motor->write(); portEXIT_CRITICAL(&motor->mux_);
    if(wait) esp_timer_start_once(motor->timer_,wait);
  }
};
} // namespace clockapp
