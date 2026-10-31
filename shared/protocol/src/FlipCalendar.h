// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "FlipPlan.h"
namespace flip {
inline bool leap(uint16_t y) { return y%4==0 && (y%100!=0 || y%400==0); }
inline uint8_t monthDays(uint16_t y,uint8_t m) {
  static const uint8_t days[12]={31,28,31,30,31,30,31,31,30,31,30,31};
  return m<1||m>12?0:uint8_t(days[m-1]+(m==2 && leap(y)));
}
inline int64_t calendarUtc(uint16_t y,uint8_t m,uint8_t d,uint8_t h,uint8_t n,uint8_t s) {
  if(y<2000 || y>2099 || m<1 || m>12 || !d || d>monthDays(y,m) || h>23 || n>59 || s>59) return -1;
  uint32_t days=10957; // 1970-01-01 -> 2000-01-01.
  for(uint16_t i=2000;i<y;++i) days+=leap(i)?366:365;
  for(uint8_t i=1;i<m;++i) days+=monthDays(y,i);
  return (int64_t(days)+d-1)*86400+int64_t(h)*3600+uint32_t(n)*60+s;
}
inline bool utcCalendar(int64_t utc,uint16_t& y,uint8_t& m,uint8_t& d,uint8_t& h,uint8_t& n,uint8_t& s) {
  if(!validUtc(utc)) return false;
  uint32_t days=uint32_t(utc/86400)-10957; y=2000;
  while(days>=uint32_t(leap(y)?366:365)) { days-=leap(y)?366:365; ++y; }
  m=1; while(days>=monthDays(y,m)) { days-=monthDays(y,m); ++m; }
  d=uint8_t(days+1); h=uint8_t((utc%86400)/3600); n=uint8_t((utc%3600)/60); s=uint8_t(utc%60); return true;
}
inline int unbcd(uint8_t b) { return (b&15)>9 || (b>>4)>9?-1:int((b>>4)*10+(b&15)); }
inline uint8_t bcd(uint8_t n) { return uint8_t((n/10)*16+n%10); }
inline int64_t decodeRtc(const uint8_t* b,uint8_t status) {
  if((status&0x80) || (b[0]&0x80) || (b[1]&0x80) || (b[2]&0xc0) || (b[5]&0xe0) || b[3]<1 || b[3]>7) return -1;
  int s=unbcd(b[0]),n=unbcd(b[1]),h=unbcd(b[2]),d=unbcd(b[4]),m=unbcd(b[5]),y=unbcd(b[6]);
  if(s<0 || n<0 || h<0 || d<0 || m<0 || y<0) return -1;
  return calendarUtc(uint16_t(2000+y),uint8_t(m),uint8_t(d),uint8_t(h),uint8_t(n),uint8_t(s));
}
} // namespace flip
