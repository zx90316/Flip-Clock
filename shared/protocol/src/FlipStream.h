// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "FlipProtocol.h"
namespace flip {
class Lines {
 public:
  char data[513];
  enum Result { MORE, LINE, TOO_LONG, TIMEOUT };
  Result push(uint8_t b,uint32_t now) {
    if(b=='\n') {
      if(discard_) { reset(); return TOO_LONG; }
      data[size_]=0; size_=0; active_=false; return LINE;
    }
    if(!active_) { active_=true; started_=now; }
    if(discard_) return MORE;
    if(size_==512 || b==0) { discard_=true; return MORE; }
    data[size_++]=char(b); return MORE;
  }
  Result tick(uint32_t now) {
    if(active_ && uint32_t(now-started_)>2000) { reset(); return TIMEOUT; }
    return MORE;
  }
  void reset() { size_=0; discard_=false; active_=false; }
 private:
  uint16_t size_=0; uint32_t started_=0; bool discard_=false,active_=false;
};
// Full request bytes are compared, so CRC collisions cannot cause a second side effect.
class Requests {
 public:
  struct Entry { uint32_t id=0; char payload[513]={}; char response[1537]={}; } entries[16];
  enum Result { NEW, REPLAY, REUSE, STALE };
  Result check(uint32_t id,const char* payload,Entry*& entry) {
    for(uint8_t i=0;i<count_;++i) if(entries[i].id==id) {
      entry=&entries[i]; return strcmp(entry->payload,payload)?REUSE:REPLAY;
    }
    if(!id || id<=watermark_) return STALE;
    entry=&entries[next_]; next_=uint8_t((next_+1)%16); if(count_<16) ++count_;
    entry->id=id; strcpy(entry->payload,payload); entry->response[0]=0; watermark_=id; return NEW;
  }
 private:
  uint32_t watermark_=0; uint8_t count_=0,next_=0;
};
} // namespace flip
