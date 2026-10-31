// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
namespace flip {
enum Op : uint8_t { OPEN=1, ARM=2, HEARTBEAT=3, MOVE=0x10, STOP=0x11, DISARM=0x12, CLEAR=0x13 };
enum State : uint8_t { BOOT=0, IDLE=1, RUNNING=2, DONE=3, STOPPED=4, FAULT=5 };
enum Error : uint8_t { OK=0, BAD_FRAME, BAD_SESSION, NOT_ARMED, BUSY, RANGE, SEQ_REUSE,
  STALE_SEQ, LINK_TIMEOUT, MOTION_TIMEOUT, RX_OVERFLOW, REVERSE_DISABLED, INTERNAL_FAULT };
inline uint16_t get16(const uint8_t* p) { return uint16_t(p[0]) | (uint16_t(p[1])<<8); }
inline uint32_t get32(const uint8_t* p) { return uint32_t(p[0]) | (uint32_t(p[1])<<8) | (uint32_t(p[2])<<16) | (uint32_t(p[3])<<24); }
inline uint64_t get64(const uint8_t* p) { return get32(p) | (uint64_t(get32(p+4))<<32); }
inline void put16(uint8_t* p, uint16_t v) { p[0]=uint8_t(v); p[1]=uint8_t(v>>8); }
inline void put32(uint8_t* p, uint32_t v) { for(uint8_t i=0;i<4;++i) p[i]=uint8_t(v>>(8*i)); }
inline void put64(uint8_t* p, uint64_t v) { put32(p,uint32_t(v)); put32(p+4,uint32_t(v>>32)); }
inline uint16_t crc16(const uint8_t* p, size_t n) {
  uint16_t c=0xffff;
  while(n--) { c^=uint16_t(*p++)<<8; for(uint8_t i=0;i<8;++i) c=(c&0x8000)?uint16_t((c<<1)^0x1021):uint16_t(c<<1); }
  return c;
}
inline uint32_t crc32(const uint8_t* p, size_t n) {
  uint32_t c=0xffffffffUL;
  while(n--) { c^=*p++; for(uint8_t i=0;i<8;++i) c=(c>>1)^((c&1)?0xedb88320UL:0); }
  return ~c;
}
inline uint32_t magnitude(int32_t v) { return v<0 ? uint32_t(-(int64_t)v):uint32_t(v); }
struct Frame {
  uint8_t bytes[32];
  Frame() { memset(bytes,0,sizeof(bytes)); bytes[0]=0xa5; bytes[1]=1; }
  uint8_t op() const { return bytes[2]; }
  uint32_t session() const { return get32(bytes+4); }
  uint32_t seq() const { return get32(bytes+8); }
  uint32_t arg(uint8_t n) const { return get32(bytes+12+4*n); }
  int32_t steps() const { uint32_t v=arg(0); return v<=0x7fffffffUL?int32_t(v):int32_t(-1-int64_t(~v)); }
  void arg(uint8_t n,uint32_t v) { put32(bytes+12+4*n,v); }
  void seal() { put16(bytes+30,crc16(bytes,30)); }
  bool valid() const { return bytes[0]==0xa5 && bytes[1]==1 && crc16(bytes,30)==get16(bytes+30); }
};
inline Frame command(Op op,uint32_t session,uint32_t seq=0) {
  Frame f; f.bytes[2]=op; put32(f.bytes+4,session); put32(f.bytes+8,seq); return f;
}
inline uint32_t isqrt(uint32_t x) {
  uint32_t root=0, bit=uint32_t(1)<<30;
  while(bit>x) bit>>=2;
  while(bit) { if(x>=root+bit) { x-=root+bit; root=(root>>1)+bit; } else root>>=1; bit>>=2; }
  return root;
}
class Endpoint {
 public:
  State state=BOOT;
  Error error=OK;
  uint32_t session=0,job=0,processed=0,remaining=0;
  int32_t executed=0;
  uint8_t phase=0xff,mask=0;
  bool armed=false,unknown=true;
  explicit Endpoint(bool reverse=false):reverse_(reverse) {}
  void handle(const Frame& f,uint32_t now) {
    if(!f.valid()) { ++badFrames; return; }
    // A late heartbeat may establish a fresh lease for CLEAR, but cannot rescue an expired armed job.
    if(armed && (!heartbeat_ || uint32_t(now-beat_)>1500)) fail(LINK_TIMEOUT);
    if(f.op()==OPEN) {
      if(!clean(f,0) || !f.session() || f.seq()) { error=BAD_FRAME; return; }
      if(f.session()==session) return;
      if(armed || state==RUNNING) { error=BUSY; return; }
      session=f.session(); processed=watermark_=0; count_=next_=0; heartbeat_=false;
      // A new generation never clears a fault or establishes mechanical position.
      if(state!=FAULT) state=IDLE;
      error=state==FAULT?error:OK; return;
    }
    if(!session || f.session()!=session) { error=BAD_SESSION; return; }
    if(f.op()==HEARTBEAT) {
      if(f.seq() || !clean(f,0)) { ++badFrames; return; }
      heartbeat_=true; beat_=now; return;
    }
    if(!f.seq()) { error=BAD_FRAME; return; }
    for(uint8_t i=0;i<count_;++i) if(cache_[i].seq==f.seq()) {
      error=memcmp(cache_[i].payload,f.bytes,30)==0?Error(cache_[i].result):SEQ_REUSE;
      processed=f.seq(); return;
    }
    if(f.seq()<=watermark_) { error=STALE_SEQ; processed=f.seq(); return; }
    Error result=apply(f,now);
    Cache& entry=cache_[next_]; entry.seq=f.seq(); memcpy(entry.payload,f.bytes,30); entry.result=result;
    next_=uint8_t((next_+1)%4); if(count_<4) ++count_;
    watermark_=f.seq(); processed=f.seq(); error=result;
  }
  void tick(uint32_t nowMs,uint32_t nowUs) {
    if(armed && (!heartbeat_ || uint32_t(nowMs-beat_)>1500)) { fail(LINK_TIMEOUT); return; }
    if(state!=RUNNING) return;
    if(uint32_t(nowMs-start_)>=timeout_) { fail(MOTION_TIMEOUT); return; }
    if(!clockStarted_) { lastUs_=nowUs; clockStarted_=true; return; }
    uint32_t distance=magnitude(executed)+1;
    if(remaining<distance) distance=remaining;
    uint32_t speed=isqrt(uint32_t(2)*accel_*distance);
    if(speed<10) speed=10;
    if(speed>rate_) speed=rate_;
    if(uint32_t(nowUs-lastUs_)<1000000UL/speed) return;
    lastUs_=nowUs; // No burst catch-up after a late loop.
    static const uint8_t phases[8]={1,3,2,6,4,12,8,9};
    phase=phase==0xff?0:uint8_t((phase+(direction_>0?1:7))&7);
    mask=phases[phase]; executed+=direction_; --remaining;
    if(!remaining) { mask=0; state=DONE; }
  }
  void fail(Error why) { if(state==RUNNING) unknown=true; mask=0; armed=false; state=FAULT; error=why; }
  Frame status(uint32_t now) const {
    Frame f; f.bytes[2]=state; f.bytes[3]=(session?1:0)|(armed?2:0)|(unknown?4:0)|(mask==0?8:0);
    put32(f.bytes+4,session); put32(f.bytes+8,job); f.arg(0,uint32_t(executed)); f.arg(1,remaining);
    f.arg(2,processed); f.arg(3,now); put16(f.bytes+28,uint16_t(error)|(uint16_t(phase)<<8)); f.seal(); return f;
  }
  uint32_t badFrames=0;
 private:
  struct Cache { uint32_t seq; uint8_t payload[30]; uint8_t result; } cache_[4];
  uint32_t watermark_=0,beat_=0,start_=0,timeout_=0,lastUs_=0,maxJob_=120000;
  uint16_t rate_=200,accel_=100,cap_=200;
  uint8_t count_=0,next_=0;
  int8_t direction_=1;
  bool reverse_=false,heartbeat_=false,clockStarted_=false;
  bool clean(const Frame& f,uint8_t used) const {
    if(f.bytes[3] || get16(f.bytes+28)) return false;
    for(uint8_t i=used;i<4;++i) if(f.arg(i)) return false;
    return true;
  }
  Error apply(const Frame& f,uint32_t now) {
    switch(f.op()) {
      case ARM:
        if(!clean(f,2)) return BAD_FRAME;
        if(state==RUNNING) return BUSY;
        if(state==FAULT || !heartbeat_ || uint32_t(now-beat_)>500) return NOT_ARMED;
        if(f.arg(0)<10 || f.arg(0)>200 || !f.arg(1) || f.arg(1)>120000UL) return RANGE;
        cap_=uint16_t(f.arg(0)); maxJob_=f.arg(1); armed=true;
        if(state==BOOT || state==STOPPED) state=IDLE;
        return OK;
      case MOVE: {
        if(!clean(f,4)) return BAD_FRAME;
        if(!armed || state==FAULT || !heartbeat_ || uint32_t(now-beat_)>1500) return NOT_ARMED;
        if(state==RUNNING) return BUSY;
        uint32_t n=magnitude(f.steps());
        if(!n || n>10000UL || f.arg(1)<10 || f.arg(1)>cap_ || f.arg(2)<1 || f.arg(2)>1000 ||
            !f.arg(3) || f.arg(3)>maxJob_) return RANGE;
        if(f.steps()<0 && !reverse_) return REVERSE_DISABLED;
        executed=0; remaining=n; direction_=f.steps()<0?-1:1;
        rate_=uint16_t(f.arg(1)); accel_=uint16_t(f.arg(2)); timeout_=f.arg(3); start_=now;
        clockStarted_=false; job=f.seq(); state=RUNNING; return OK;
      }
      case STOP:
        if(!clean(f,0)) return BAD_FRAME;
        if(state==RUNNING) unknown=true;
        mask=0; armed=false; if(state!=FAULT) state=STOPPED; return OK;
      case DISARM:
        if(!clean(f,0)) return BAD_FRAME;
        if(state==RUNNING) return BUSY;
        mask=0; armed=false; return OK;
      case CLEAR:
        if(!clean(f,0)) return BAD_FRAME;
        if(state==RUNNING || armed) return BUSY;
        if(!heartbeat_ || uint32_t(now-beat_)>500) return NOT_ARMED;
        mask=0; state=IDLE; unknown=true; return OK;
      default: return BAD_FRAME;
    }
  }
};
} // namespace flip
