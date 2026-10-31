// SPDX-License-Identifier: GPL-3.0-only
#include <FlipProtocol.h>
#include <FlipBench.h>
#include <FlipPlan.h>
#include <FlipStorage.h>
#include <FlipStream.h>
#include <FlipCalendar.h>
#include <assert.h>
#include <stdio.h>
#include <string>
using namespace flip;
static unsigned checks=0;
#define CHECK(x) do { ++checks; if(!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); return 1; } } while(0)
Frame make(Op op,uint32_t seq=0,uint32_t a=0,uint32_t b=0,uint32_t c=0,uint32_t d=0,uint32_t session=42) {
  Frame f=command(op,session,seq); f.arg(0,a); f.arg(1,b); f.arg(2,c); f.arg(3,d); f.seal(); return f;
}
void openArm(Endpoint& e,uint32_t now=0) {
  e.handle(make(OPEN),now); e.handle(make(HEARTBEAT),now); e.handle(make(ARM,1,200,120000),now);
}
uint32_t complete(Endpoint& e,uint32_t start=0) {
  uint32_t end=start;
  for(uint32_t us=0;us<120000000UL && e.state==RUNNING;us+=1000) {
    if(us%250000==0) e.handle(make(HEARTBEAT),start+us/1000);
    e.tick(start+us/1000,us);
    end=start+us/1000;
  }
  return end;
}
int main() {
  CHECK(crc16((const uint8_t*)"123456789",9)==0x29b1);
  CHECK(crc32((const uint8_t*)"123456789",9)==0xcbf43926UL);
  Frame move=make(MOVE,2,136,200,100,20000);
  CHECK(move.valid());
  const char* golden="a50110002a0000000200000088000000c800000064000000204e000000007d80";
  for(unsigned i=0;i<32;++i) { unsigned v=0; sscanf(golden+2*i,"%2x",&v); CHECK(move.bytes[i]==v); }
  for(unsigned i=0;i<32;++i) for(unsigned bit=0;bit<8;++bit) {
    Frame bad=move; bad.bytes[i]^=uint8_t(1<<bit); Endpoint e; openArm(e); e.handle(bad,1);
    CHECK(e.state!=RUNNING); CHECK(!bad.valid());
  }
  Endpoint e; CHECK(e.mask==0 && !e.armed && e.session==0);
  e.handle(move,0); CHECK(e.state==BOOT && e.error==BAD_SESSION);
  e.handle(make(OPEN),0); e.handle(make(ARM,1,200,120000),0); CHECK(!e.armed && e.error==NOT_ARMED);
  e.handle(make(HEARTBEAT),1); e.handle(make(ARM,2,200,120000),1); CHECK(e.armed);
  auto m=make(MOVE,3,136,200,100,20000); e.handle(m,1); CHECK(e.state==RUNNING);
  e.handle(m,2); CHECK(e.executed==0 && e.remaining==136);
  auto changed=m; changed.arg(0,137); changed.seal(); e.handle(changed,3); CHECK(e.error==SEQ_REUSE && e.remaining==136);
  e.handle(m,3); uint32_t finished=complete(e,3); CHECK(e.state==DONE && e.executed==136 && e.mask==0);
  uint8_t phase=e.phase; e.handle(m,finished+1); CHECK(e.state==DONE && e.executed==136 && e.phase==phase);
  e.handle(make(HEARTBEAT),finished+2); CHECK(e.state==DONE && e.executed==136 && e.job==3);
  e.handle(make(OPEN),finished+3); CHECK(e.job==3 && e.processed==3);
  for(uint32_t i=4;i<=9;++i) e.handle(make(DISARM,i),finished+4);
  e.handle(m,finished+5); CHECK(e.error==STALE_SEQ && e.executed==136 && e.job==3);
  e.handle(make(OPEN,0,0,0,0,0,77),finished+6); CHECK(e.session==77 && e.unknown && e.processed==0);
  Endpoint lease; openArm(lease,0xfffffff0UL); lease.handle(make(MOVE,2,1000,200,100,20000),0xfffffff0UL);
  lease.tick(0xfffffff0UL+1501UL,2000000); CHECK(lease.state==FAULT && lease.error==LINK_TIMEOUT && !lease.armed && lease.mask==0);
  lease.handle(make(HEARTBEAT),2000); CHECK(lease.state==FAULT && !lease.armed);
  Endpoint lateBeat; openArm(lateBeat); lateBeat.handle(make(MOVE,2,1000,200,100,20000),0);
  lateBeat.handle(make(HEARTBEAT),1501); CHECK(lateBeat.state==FAULT && !lateBeat.armed && lateBeat.mask==0);
  Endpoint timeout; openArm(timeout); timeout.handle(make(MOVE,2,100,200,100,5),0); timeout.tick(5,5000);
  CHECK(timeout.state==FAULT && timeout.error==MOTION_TIMEOUT && !timeout.mask);
  Endpoint invalid; openArm(invalid); auto flag=make(MOVE,2,1,100,100,1000); flag.bytes[3]=1; flag.seal(); invalid.handle(flag,0);
  CHECK(invalid.error==BAD_FRAME && invalid.state!=RUNNING);
  invalid.handle(make(MOVE,3,uint32_t(-1),100,100,1000),0); CHECK(invalid.error==REVERSE_DISABLED);
  invalid.handle(make(MOVE,4,1,201,100,1000),0); CHECK(invalid.error==RANGE);
  invalid.handle(make(MOVE,5,0x80000000UL,100,100,1000),0); CHECK(invalid.error==RANGE);
  // High-speed profile: new limits, and the motor must ramp up from rest and ramp down before arrival.
  {
    Endpoint fast; fast.handle(make(OPEN),0); fast.handle(make(HEARTBEAT),0);
    fast.handle(make(ARM,1,1001,120000),0); CHECK(fast.error==RANGE && !fast.armed);
    fast.handle(make(ARM,2,1000,120000),0); CHECK(fast.armed);
    fast.handle(make(MOVE,3,1000,1001,100,60000),0); CHECK(fast.error==RANGE && fast.state!=RUNNING);
    fast.handle(make(MOVE,4,1000,800,4001,60000),0); CHECK(fast.error==RANGE && fast.state!=RUNNING);
    fast.handle(make(MOVE,5,10001,800,2000,60000),0); CHECK(fast.error==RANGE);
    fast.handle(make(MOVE,6,3000,800,2000,60000),0); CHECK(fast.state==RUNNING);
    uint32_t last=0,first=0,minGap=0xffffffffUL,lastGap=0,steps=0,done=0;
    for(uint32_t us=0;us<60000000UL && fast.state==RUNNING;us+=100) {
      if(us%250000==0) fast.handle(make(HEARTBEAT),us/1000);
      int32_t before=fast.executed; fast.tick(us/1000,us);
      if(fast.executed!=before) {
        if(steps==1) first=us-last; // gap between step 1 and step 2: start of the ramp
        if(steps>1 && us-last<minGap) minGap=us-last;
        lastGap=us-last; last=us; ++steps; done=us;
      }
    }
    CHECK(fast.state==DONE && fast.executed==3000 && !fast.mask);
    CHECK(first>8000 && lastGap>4000);          // slow at the start and just before stopping (>= 4 ms/step = <250 steps/s)
    CHECK(minGap<=1300 && minGap>=1000);        // cruise reaches the 800..1000 steps/s window (loop granularity 0.1 ms)
    CHECK(done<5500000UL);                      // far faster than 3000 steps at the old 200 steps/s limit (15 s)
  }
  Endpoint stop; openArm(stop); stop.handle(make(MOVE,2,1000,200,100,20000),0);
  for(uint32_t us=0;us<=200000;us+=1000) stop.tick(us/1000,us);
  CHECK(stop.executed>0 && stop.executed<1000); int32_t partial=stop.executed;
  stop.handle(make(STOP,3),201); CHECK(stop.executed==partial && stop.mask==0 && !stop.armed && stop.unknown);
  stop.handle(make(MOVE,2,1000,200,100,20000),202); CHECK(stop.state==STOPPED && stop.executed==partial);
  Endpoint micro; openArm(micro); micro.handle(make(MOVE,2,2,10,1,20000),0);
  micro.tick(0,0xffff0000UL); micro.tick(200,0xffff0000UL+200000UL); CHECK(micro.executed==1);
  micro.tick(400,0xffff0000UL+400000UL); CHECK(micro.executed==2 && micro.state==DONE);
  Endpoint reset; openArm(reset); reset.handle(make(MOVE,2,100,100,100,20000),0); reset=Endpoint(); reset.handle(make(MOVE,2,100,100,100,20000),0);
  CHECK(reset.session==0 && reset.state==BOOT && reset.mask==0);
  Endpoint many; openArm(many,2000);
  for(uint32_t seq=2;seq<20;++seq) {
    many.handle(make(HEARTBEAT),seq*1000);
    many.handle(make(MOVE,seq,5,200,100,20000),seq*1000); complete(many,seq*1000);
    CHECK(many.state==DONE && many.executed==5 && many.mask==0);
  }
  CHECK(many.phase==uint8_t((18*5-1)%8));
  Endpoint overflow; openArm(overflow); overflow.fail(RX_OVERFLOW); CHECK(!overflow.armed && overflow.mask==0 && overflow.state==FAULT);
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
  Planner p; CHECK(!p.position && p.paused); p.config.mechanics=true; p.setDisplay(1);
  int64_t utc=calendarUtc(2026,10,31,16,0,0); CHECK(p.makePreview(utc,1,123));
  CHECK(p.preview.pages==719 && p.preview.large); CHECK(!p.resume(123,false,utc,2));
  CHECK(!p.resume(123,true,utc+60,2)); CHECK(p.resume(123,true,utc,2));
  CHECK(p.commit(2,999) && p.display==2 && p.remainder==999); CHECK(!p.commit(2,999) && p.display==2);
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
  Endpoint benchMotor; BenchGate gate;
  CHECK(!gate.submit(make(OPEN),benchMotor,0)); CHECK(gate.enable(benchMotor));
  CHECK(gate.submit(make(OPEN),benchMotor,0)); CHECK(gate.submit(make(HEARTBEAT),benchMotor,0));
  CHECK(!gate.submit(make(ARM,1,51,10000),benchMotor,0));
  CHECK(gate.submit(make(ARM,1,30,10000),benchMotor,0));
  CHECK(!gate.submit(make(MOVE,2,257,30,100,10000),benchMotor,0));
  CHECK(gate.submit(make(MOVE,2,16,30,100,10000),benchMotor,0));
  gate.masterActivity(benchMotor); CHECK(!gate.enabled && !benchMotor.armed && !benchMotor.mask);
  CHECK(!gate.enable(benchMotor));
  printf("PASS core: %u checks; protocol, replay, lease, rollover, planner, calendar, NVS, BLE stream\n",checks);
  return 0;
}
