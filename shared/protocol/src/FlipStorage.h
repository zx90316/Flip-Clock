// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "FlipPlan.h"
namespace flip {
// No ABI padding: 80 bytes, LE; CRC32 over offsets 0..75, CRC at 76..79.
struct Saved {
  Config config;
  uint32_t generation=0,r=0,snapshotGeneration=0;
  uint16_t display=0,snapshotCycle=720;
  int64_t utc=0;
  uint8_t phase=0xff,source=0;
  bool hasSnapshot=false;
};
static const size_t BLOB_SIZE=80;
inline void encodeSaved(const Saved& s,uint8_t* b) {
  memset(b,0,BLOB_SIZE); memcpy(b,"FCLK",4); put16(b+4,1); put16(b+6,BLOB_SIZE); put32(b+8,s.generation);
  put64(b+12,s.config.q); put16(b+20,s.config.cycle); put16(b+22,s.config.rate); put16(b+24,s.config.accel);
  put16(b+26,s.config.settle); put16(b+28,uint16_t(s.config.offset)); put16(b+30,s.config.maxPages);
  put16(b+32,s.config.maxSeconds); put16(b+34,s.config.checkpoint);
  b[36]=s.config.mechanics; b[37]=s.config.reverse; b[38]=s.config.autoTime; b[39]=uint8_t(s.config.direction);
  b[40]=s.hasSnapshot; b[41]=s.phase; put16(b+42,s.display); put32(b+44,s.r); put64(b+48,uint64_t(s.utc));
  b[56]=1; // board profile AI_THINKER_ESP32_CAM_DUAL_UNO; fixed release_coils and SAFE_RECONFIRM.
  put32(b+57,s.snapshotGeneration); b[61]=s.source; put16(b+62,s.snapshotCycle); put16(b+64,uint16_t(s.config.trim));
  put32(b+76,crc32(b,76));
}
inline bool decodeSaved(const uint8_t* b,size_t n,Saved& out) {
  if(n!=BLOB_SIZE || memcmp(b,"FCLK",4) || get16(b+4)!=1 || get16(b+6)!=BLOB_SIZE ||
     get32(b+76)!=crc32(b,76) || b[56]!=1 || b[36]>1 || b[37]>1 || b[38]>1 || b[40]>1) return false;
  for(uint8_t i=66;i<76;++i) if(b[i]) return false;
  Saved s; s.generation=get32(b+8); s.config.q=get64(b+12); s.config.cycle=get16(b+20); s.config.rate=get16(b+22);
  s.config.accel=get16(b+24); s.config.settle=get16(b+26); s.config.offset=int16_t(get16(b+28));
  s.config.maxPages=get16(b+30); s.config.maxSeconds=get16(b+32); s.config.checkpoint=get16(b+34);
  s.config.mechanics=b[36]; s.config.reverse=b[37]; s.config.autoTime=b[38]; s.config.direction=b[39]==255?-1:int8_t(b[39]);
  s.hasSnapshot=b[40]; s.phase=b[41]; s.display=get16(b+42); s.r=get32(b+44); s.utc=int64_t(get64(b+48));
  s.snapshotGeneration=get32(b+57); s.source=b[61]; s.snapshotCycle=get16(b+62); s.config.trim=int16_t(get16(b+64));
  if(!s.config.valid() || !s.generation || s.r>=D || (s.snapshotCycle!=720 && s.snapshotCycle!=1440) || s.display>=s.snapshotCycle ||
     (s.phase>7 && s.phase!=255) || s.source>2 ||
     (s.hasSnapshot && (!validUtc(s.utc) || !s.snapshotGeneration || s.snapshotGeneration>s.generation))) return false;
  out=s; return true;
}
inline int selectSlot(const uint8_t* a,size_t an,const uint8_t* b,size_t bn,Saved& out) {
  Saved x,y; bool ax=decodeSaved(a,an,x),by=decodeSaved(b,bn,y);
  if(!ax && !by) return -1;
  if(ax && (!by || x.generation>=y.generation)) { out=x; return 0; }
  out=y; return 1;
}
} // namespace flip
