// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
namespace flip {
// Half-steps per second / per second squared. A move always ramps up from rest and down to rest:
// speed = min(rate, sqrt(2*accel*min(distance from start, distance to go))).
static const uint16_t MAX_RATE=1000,MAX_ACCEL=4000;
static const uint32_t MAX_MOVE_STEPS=10000;
inline uint16_t get16(const uint8_t* p) { return uint16_t(p[0]) | (uint16_t(p[1])<<8); }
inline uint32_t get32(const uint8_t* p) { return uint32_t(p[0]) | (uint32_t(p[1])<<8) | (uint32_t(p[2])<<16) | (uint32_t(p[3])<<24); }
inline uint64_t get64(const uint8_t* p) { return get32(p) | (uint64_t(get32(p+4))<<32); }
inline void put16(uint8_t* p, uint16_t v) { p[0]=uint8_t(v); p[1]=uint8_t(v>>8); }
inline void put32(uint8_t* p, uint32_t v) { for(uint8_t i=0;i<4;++i) p[i]=uint8_t(v>>(8*i)); }
inline void put64(uint8_t* p, uint64_t v) { put32(p,uint32_t(v)); put32(p+4,uint32_t(v>>32)); }
inline uint32_t crc32(const uint8_t* p, size_t n) {
  uint32_t c=0xffffffffUL;
  while(n--) { c^=*p++; for(uint8_t i=0;i<8;++i) c=(c>>1)^((c&1)?0xedb88320UL:0); }
  return ~c;
}
inline uint32_t magnitude(int32_t v) { return v<0 ? uint32_t(-(int64_t)v):uint32_t(v); }
inline uint32_t isqrt(uint32_t x) {
  uint32_t root=0, bit=uint32_t(1)<<30;
  while(bit>x) bit>>=2;
  while(bit) { if(x>=root+bit) { x-=root+bit; root=(root>>1)+bit; } else root>>=1; bit>>=2; }
  return root;
}
// One forward half-step move at a time. Holds no hardware: the caller writes `mask` to the coils and waits
// the period step() returns. Coils are released one period after the last step, so the rotor settles there.
class Motion {
 public:
  enum State : uint8_t { IDLE, RUNNING, DONE, FAULT };
  State state=IDLE;
  uint32_t remaining=0,moves=0;
  int32_t executed=0;
  uint8_t phase=0xff,mask=0; // phase survives between moves so the next move continues the coil sequence
  bool start(uint32_t steps,uint16_t rate,uint16_t accel,uint32_t timeoutMs,uint32_t nowMs) {
    if(state==RUNNING || state==FAULT || !steps || steps>MAX_MOVE_STEPS || rate<10 || rate>MAX_RATE ||
       !accel || accel>MAX_ACCEL || !timeoutMs) return false;
    executed=0; remaining=steps; rate_=rate; accel_=accel; timeout_=timeoutMs; start_=nowMs; state=RUNNING; ++moves;
    return true;
  }
  // Advances one half-step. Returns microseconds until the next call, or 0 when the move has ended.
  uint32_t step() {
    if(state!=RUNNING) return 0;
    if(!remaining) { mask=0; state=DONE; return 0; }
    uint32_t distance=uint32_t(executed)+1;
    if(remaining<distance) distance=remaining;
    uint32_t speed=isqrt(uint32_t(2)*accel_*distance);
    if(speed<10) speed=10;
    if(speed>rate_) speed=rate_;
    static const uint8_t phases[8]={1,3,2,6,4,12,8,9};
    phase=phase==0xff?0:uint8_t((phase+1)&7);
    mask=phases[phase]; ++executed; --remaining;
    return 1000000UL/speed;
  }
  bool timedOut(uint32_t nowMs) const { return state==RUNNING && uint32_t(nowMs-start_)>=timeout_; }
  void stop() { mask=0; remaining=0; if(state!=FAULT) state=IDLE; }
  void fail() { mask=0; remaining=0; state=FAULT; }
  void acknowledge() { if(state==DONE) state=IDLE; }
  void clear() { mask=0; remaining=0; state=IDLE; }
 private:
  uint32_t start_=0,timeout_=0;
  uint16_t rate_=200,accel_=100;
};
} // namespace flip
