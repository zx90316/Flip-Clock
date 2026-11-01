// SPDX-License-Identifier: GPL-3.0-only
#include <FlipProtocol.h>
#include <FlipPlan.h>
#include <FlipStorage.h>
#include <FlipStream.h>
#include <FlipCalendar.h>
#include <assert.h>
#include <stdio.h>
#include <string>
#include <vector>
using namespace flip;
static unsigned checks=0;
#define CHECK(x) do { ++checks; if(!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); return 1; } } while(0)
// Runs a move to its end the way the firmware's timer does; returns the elapsed microseconds.
uint64_t run(Motion& m) { uint64_t us=0; for(uint32_t wait=m.step();wait;wait=m.step()) us+=wait; return us; }
int main() {
  CHECK(crc32((const uint8_t*)"123456789",9)==0xcbf43926UL);
  { // Limits: nothing starts outside them, and a refused start changes nothing.
    Motion m; CHECK(m.state==Motion::IDLE && m.mask==0);
    CHECK(!m.start(0,200,100,1000,0) && !m.start(MAX_MOVE_STEPS+1,200,100,1000,0) && !m.start(1,9,100,1000,0) && !m.start(1,1001,100,1000,0));
    CHECK(!m.start(1,200,0,1000,0) && !m.start(1,200,4001,1000,0) && !m.start(1,200,100,0,0) && m.state==Motion::IDLE && !m.moves);
    CHECK(m.step()==0 && m.mask==0);
    CHECK(m.start(136,200,100,20000,0) && m.state==Motion::RUNNING && !m.start(1,200,100,1000,0) && m.remaining==136);
    run(m); CHECK(m.state==Motion::DONE && m.executed==136 && !m.remaining && !m.mask);
    uint8_t phase=m.phase; CHECK(m.step()==0 && m.phase==phase); m.acknowledge(); CHECK(m.state==Motion::IDLE);
  }
  { // Half-step coil sequence: one or two adjacent coils, and it carries across moves.
    Motion m; static const uint8_t expected[8]={1,3,2,6,4,12,8,9};
    for(unsigned i=0;i<20;++i) { CHECK(m.start(1,200,100,1000,0)); m.step(); CHECK(m.mask==expected[i%8] && m.phase==i%8); CHECK(m.step()==0 && !m.mask); m.acknowledge(); }
  }
  { // A restored phase continues exactly one half-step on from where the rotor stopped.
    Motion m; m.phase=7; CHECK(m.start(1,200,100,1000,0)); m.step(); CHECK(m.phase==0 && m.mask==1);
  }
  { // High-speed profile: must ramp up from rest and ramp down before arrival.
    Motion m; CHECK(m.start(3000,800,2000,60000,0));
    std::vector<uint32_t> gaps; for(uint32_t wait=m.step();wait;wait=m.step()) gaps.push_back(wait);
    CHECK(gaps.size()==3000 && m.executed==3000 && !m.mask && m.state==Motion::DONE);
    uint32_t fastest=0xffffffffUL; uint64_t total=0; for(uint32_t g:gaps) { if(g<fastest) fastest=g; total+=g; }
    CHECK(gaps.front()>8000 && gaps.back()>8000);  // slow at the start and just before stopping
    CHECK(fastest==1250);                          // cruise is exactly the 800 steps/s limit
    CHECK(total<5500000ULL);                       // far faster than 3000 steps at 200 steps/s (15 s)
    for(size_t i=1;i<1500;++i) CHECK(gaps[i]<=gaps[i-1]);
  }
  { // Stop, fault and timeout all release the coils at once, across a millis() wrap too.
    Motion m; CHECK(m.start(1000,200,100,20000,0)); for(int i=0;i<10;++i) m.step(); CHECK(m.mask);
    m.stop(); CHECK(m.state==Motion::IDLE && !m.mask && m.executed==10 && m.step()==0);
    Motion t; uint32_t at=0xfffffff0UL; CHECK(t.start(100,200,100,5,at)); CHECK(!t.timedOut(at+4)); CHECK(t.timedOut(at+5));
    t.step(); t.fail(); CHECK(t.state==Motion::FAULT && !t.mask && t.step()==0);
    CHECK(!t.start(1,200,100,1000,0)); t.stop(); CHECK(t.state==Motion::FAULT); t.clear(); CHECK(t.state==Motion::IDLE && t.start(1,200,100,1000,0));
  }
  uint32_t steps,r; CHECK(pageSteps(136533333ULL,0,30,steps,r) && steps==4095 && r==999990);
  uint32_t total=0,rem=0;
  for(unsigned i=0;i<30;++i) { uint32_t n,nr; CHECK(pageSteps(136533333ULL,rem,1,n,nr)); total+=n; rem=nr; }
  CHECK(total==steps && rem==r);
  CHECK(pageSteps(10000000000ULL,999999,1440,steps,r) && steps==14400000 && r==999999);
  CHECK(!pageSteps(10000000001ULL,0,1,steps,r));
  for(uint32_t i=0;i<20000;++i) { uint32_t root=isqrt(i); CHECK(root*root<=i && (root+1)*(root+1)>i); }
  Config c; CHECK(c.valid());
  CHECK(calendarUtc(2000,2,29,0,0,0)==951782400LL);
  CHECK(calendarUtc(2100,1,1,0,0,0)==-1); CHECK(calendarUtc(2023,2,29,0,0,0)==-1);
  for(uint16_t y=2000;y<2100;++y) for(uint8_t m=1;m<=12;++m) {
    int64_t utc=calendarUtc(y,m,monthDays(y,m),23,59,59); uint16_t yy; uint8_t mm,d,h,n,s;
    CHECK(utcCalendar(utc,yy,mm,d,h,n,s) && yy==y && mm==m && d==monthDays(y,m) && h==23 && n==59 && s==59);
  }
  CHECK(target(calendarUtc(2026,10,31,16,0,0),c)==0);
  c.cycle=1440; CHECK(target(calendarUtc(2026,10,31,15,59,0),c)==1439);
  CHECK(target(calendarUtc(2026,10,31,16,0,0),c)==0);
  c.offset=-720; CHECK(target(calendarUtc(2000,1,1,0,0,0),c)==720);
  uint8_t date[7]={0,0,0,7,0x31,0x10,0x26}; CHECK(validUtc(decodeRtc(date,0)));
  CHECK(decodeRtc(date,0x80)==-1); date[5]=0x90; CHECK(decodeRtc(date,0)==-1);
  Planner p; CHECK(!p.position && p.paused); p.config.mechanics=true; p.setDisplay(100);
  int64_t utc=calendarUtc(2026,10,31,16,0,0); CHECK(p.makePreview(utc,1,123));
  CHECK(p.preview.pages==620 && p.preview.large); CHECK(!p.resume(123,false,utc,2));
  CHECK(!p.resume(123,true,utc+60,2)); CHECK(p.resume(123,true,utc,2));
  CHECK(p.commit(2,999) && p.display==101 && p.remainder==999); CHECK(!p.commit(2,999) && p.display==101);
  { Config hc; hc.offset=480; int64_t t0=calendarUtc(2026,10,31,16,0,0); // target page 0; a display slightly ahead waits, it does not spin a whole cycle
    CHECK(pagesBehind(t0,hc,0)==0 && pagesBehind(t0,hc,1)==0 && pagesBehind(t0,hc,AHEAD_HOLD)==0 && pagesBehind(t0,hc,10)==0);
    CHECK(pagesBehind(t0,hc,AHEAD_HOLD+1)==hc.cycle-AHEAD_HOLD-1 && pagesBehind(t0,hc,hc.cycle-1)==1 && pagesBehind(t0,hc,hc.cycle-5)==5);
    CHECK(pagesBehind(t0+120,hc,1)==1 && pagesBehind(t0+60,hc,1)==0 && pagesBehind(t0+60,hc,0)==1); }
  p.changed(false); CHECK(p.paused && p.position); CHECK(!p.resume(123,true,utc,3));
  p.changed(true); CHECK(!p.position); p.setDisplay(719); CHECK(p.commit(1,0) && p.display==0);
  p.invalidate(); CHECK(!p.position && p.paused && !p.committed);
  Saved saved; saved.generation=1; uint8_t a[BLOB_SIZE],b[BLOB_SIZE]; encodeSaved(saved,a); Saved decoded;
  CHECK(decodeSaved(a,sizeof(a),decoded) && decoded.config.q==saved.config.q);
  for(size_t cut=0;cut<BLOB_SIZE;++cut) CHECK(!decodeSaved(a,cut,decoded));
  for(size_t i=0;i<BLOB_SIZE;++i) { memcpy(b,a,sizeof(b)); b[i]^=1; CHECK(!decodeSaved(b,sizeof(b),decoded)); }
  saved.generation=2; encodeSaved(saved,b); CHECK(selectSlot(a,sizeof(a),b,sizeof(b),decoded)==1 && decoded.generation==2);
  b[70]^=1; CHECK(selectSlot(a,sizeof(a),b,sizeof(b),decoded)==0 && decoded.generation==1);
  CHECK(selectSlot(a,0,b,0,decoded)==-1);
  Lines lines; std::string utf8="{\"text\":\"繁體中文\"}\n"; unsigned completeLines=0;
  for(size_t i=0;i<utf8.size();++i) if(lines.push(uint8_t(utf8[i]),uint32_t(i))==Lines::LINE) ++completeLines;
  CHECK(completeLines==1 && std::string(lines.data)==utf8.substr(0,utf8.size()-1));
  for(unsigned i=0;i<513;++i) lines.push('a',0); CHECK(lines.push('\n',0)==Lines::TOO_LONG);
  CHECK(lines.push('{',0xfffffff0UL)==Lines::MORE); CHECK(lines.tick(0xfffffff0UL+2001UL)==Lines::TIMEOUT);
  Requests ids; Requests::Entry* entry=nullptr;
  CHECK(ids.check(1,"A",entry)==Requests::NEW); strcpy(entry->response,"accepted");
  CHECK(ids.check(1,"A",entry)==Requests::REPLAY && !strcmp(entry->response,"accepted"));
  CHECK(ids.check(1,"B",entry)==Requests::REUSE);
  for(uint32_t i=2;i<=20;++i) CHECK(ids.check(i,"C",entry)==Requests::NEW);
  CHECK(ids.check(1,"A",entry)==Requests::STALE);
  CHECK(ids.check(0xffffffffUL,"D",entry)==Requests::NEW); CHECK(ids.check(1,"A",entry)==Requests::STALE);
  printf("PASS core: %u checks; motion, planner, calendar, NVS, BLE stream\n",checks);
  return 0;
}
