// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "FlipProtocol.h"
namespace flip {
static const uint32_t D=1000000UL;
struct Config {
  uint64_t q=136000000ULL;
  uint16_t cycle=720,rate=200,accel=100,settle=200,maxPages=60,maxSeconds=120,checkpoint=30;
  int16_t offset=480;
  bool mechanics=false,reverse=false,autoTime=true;
  int8_t direction=1;
  bool valid() const { return q>=D && q<=10000ULL*D && (cycle==720 || cycle==1440) &&
    rate>=10 && rate<=200 && accel>=1 && accel<=1000 && settle<=5000 && offset>=-720 && offset<=840 &&
    maxPages>=1 && maxPages<=60 && maxSeconds>=1 && maxSeconds<=120 && checkpoint<=1440 &&
    (direction==1 || direction==-1); }
};
inline int64_t floorDiv(int64_t a,int64_t b) { return a>=0?a/b:-((-a+b-1)/b); }
inline uint16_t modPos(int64_t a,uint16_t p) { int64_t m=a%p; return uint16_t(m<0?m+p:m); }
inline bool validUtc(int64_t utc) { return utc>=946684800LL && utc<=4102444799LL; }
inline uint16_t target(int64_t utc,const Config& c) { return modPos(floorDiv(utc+int64_t(c.offset)*60,60),c.cycle); }
inline bool pageSteps(uint64_t q,uint32_t r,uint32_t pages,uint32_t& steps,uint32_t& next) {
  if(q<D || q>10000ULL*D || r>=D || !pages || pages>1440) return false;
  uint64_t total=uint64_t(r)+uint64_t(pages)*q;
  steps=uint32_t(total/D); next=uint32_t(total%D); return true;
}
inline uint32_t estimateMs(uint32_t steps,const Config& c) {
  // Conservative bound: cruise plus full accel/decel allowance and settle per page.
  return uint32_t((uint64_t(steps)*1000+c.rate-1)/c.rate)+
         uint32_t((uint32_t(c.rate)*2000+c.accel-1)/c.accel)+c.settle;
}
struct Preview { uint32_t id=0,revision=0,created=0,estimate=0; int64_t minute=0; uint16_t pages=0; bool large=false; };
class Planner {
 public:
  Config config;
  uint32_t revision=1,remainder=0,committed=0;
  uint16_t display=0;
  bool position=false,paused=true,manualPause=false;
  void invalidate() { position=false; paused=true; committed=0; ++revision; preview.id=0; }
  void setDisplay(uint16_t value) { display=value; remainder=0; committed=0; position=true; paused=true; ++revision; preview.id=0; }
  void changed(bool geometry) { paused=true; ++revision; preview.id=0; if(geometry) position=false; }
  bool makePreview(int64_t utc,uint32_t now,uint32_t id) {
    if(!config.valid() || !config.mechanics || !position || !validUtc(utc)) return false;
    preview.id=id?id:1; preview.revision=revision; preview.created=now;
    preview.minute=floorDiv(utc+int64_t(config.offset)*60,60);
    preview.pages=modPos(int64_t(target(utc,config))-display,config.cycle);
    uint32_t steps=0,next=0;
    if(preview.pages) pageSteps(config.q,remainder,1,steps,next);
    preview.estimate=uint32_t(uint64_t(estimateMs(steps,config))*preview.pages);
    preview.large=preview.pages>config.maxPages || preview.estimate>uint32_t(config.maxSeconds)*1000;
    return true;
  }
  bool resume(uint32_t id,bool large,int64_t utc,uint32_t now) {
    if(!preview.id || id!=preview.id || revision!=preview.revision || uint32_t(now-preview.created)>30000 ||
       floorDiv(utc+int64_t(config.offset)*60,60)!=preview.minute || (preview.large && !large)) return false;
    paused=false; manualPause=false; preview.id=0; return true;
  }
  bool commit(uint32_t job,uint32_t next) {
    if(!position || !job || job<=committed || next>=D) return false;
    display=uint16_t((display+1)%config.cycle); remainder=next; committed=job; ++revision; return true;
  }
  Preview preview;
};
} // namespace flip
