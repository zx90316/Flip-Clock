// SPDX-License-Identifier: GPL-3.0-only
#include <Wire.h>
#include <avr/wdt.h>
#include <util/atomic.h>
#include <FlipProtocol.h>
#include <FlipBench.h>

#ifndef FLIP_ALLOW_REVERSE
#define FLIP_ALLOW_REVERSE 0
#endif
// Capture reset cause and disable WDT before setup. Optiboot compatibility still needs H09.
uint8_t resetCause __attribute__((section(".noinit")));
void earlyReset() __attribute__((naked,used,section(".init3")));
void earlyReset() { resetCause=MCUSR; MCUSR=0; wdt_disable(); }
flip::Endpoint endpoint(FLIP_ALLOW_REVERSE);
volatile uint8_t rx[2][32],rxLength[2],head=0,tail=0,queued=0;
volatile bool overflow=false;
uint8_t snapshots[2][32];
volatile uint8_t activeSnapshot=0;
flip::BenchGate bench;
volatile bool i2cSeen=false;
char serialCommand[80];
uint8_t serialLength=0;
bool serialDiscard=false;

void printStatus() {
  // Diagnostic output is allowed only while disarmed, so printing cannot delay motion.
  if(endpoint.armed || endpoint.state==flip::RUNNING) {
    if(Serial.availableForWrite()>=8) Serial.println(F("BUSY"));
    return;
  }
  Serial.print(F("{\"board\":\"UNO\",\"firmware\":\"0.2.0\",\"protocol\":1,\"state\":"));
  Serial.print(uint8_t(endpoint.state)); Serial.print(F(",\"armed\":false,\"coil_mask\":")); Serial.print(endpoint.mask);
  Serial.print(F(",\"session\":")); Serial.print(endpoint.session);
  Serial.print(F(",\"executed\":")); Serial.print(endpoint.executed);
  Serial.print(F(",\"remaining\":")); Serial.print(endpoint.remaining);
  Serial.print(F(",\"reset_cause\":")); Serial.print(resetCause); Serial.println('}');
}
int8_t hexNibble(char c) {
  if(c>='0' && c<='9') return c-'0';
  if(c>='a' && c<='f') return c-'a'+10;
  if(c>='A' && c<='F') return c-'A'+10;
  return -1;
}
void printFrame() {
  flip::Frame f=endpoint.status(millis());
  const char* hex="0123456789abcdef";
  Serial.print(F("F "));
  for(uint8_t i=0;i<32;++i) { Serial.write(hex[f.bytes[i]>>4]); Serial.write(hex[f.bytes[i]&15]); }
  Serial.write('\n');
}
void serviceSerial() {
  for(uint8_t n=0;n<16 && Serial.available();++n) {
    char c=char(Serial.read()); if(c=='\r') continue;
    if(c=='\n') {
      serialCommand[serialLength]=0;
      if(!serialDiscard && !strcmp(serialCommand,"STOP")) {
        endpoint.fail(flip::INTERNAL_FAULT); PORTB &= 0xf0;
        Serial.println(F("LOCAL_STOP: outputs low; fault latched"));
      } else if(!serialDiscard && !strcmp(serialCommand,"STATUS")) printStatus();
      else if(!serialDiscard && !strcmp(serialCommand,"BENCH ON")) Serial.println(bench.enable(endpoint)?F("BENCH_ON"):F("E_BENCH_LOCKED"));
      else if(!serialDiscard && !strcmp(serialCommand,"BENCH OFF")) { bench.disable(endpoint); PORTB=uint8_t((PORTB&0xf0)|endpoint.mask); Serial.println(F("BENCH_OFF")); }
      else if(!serialDiscard && !strcmp(serialCommand,"POLL") && bench.enabled) printFrame();
      else if(!serialDiscard && !strncmp(serialCommand,"FRAME ",6) && serialLength==70) {
        flip::Frame f; bool valid=true;
        for(uint8_t i=0;i<32;++i) {
          int8_t hi=hexNibble(serialCommand[6+2*i]),lo=hexNibble(serialCommand[7+2*i]);
          if(hi<0 || lo<0) { valid=false; break; }
          f.bytes[i]=uint8_t((hi<<4)|lo);
        }
        if(valid && bench.submit(f,endpoint,millis())) printFrame();
        else Serial.println(F("E_BENCH_FRAME"));
      }
      else if(!endpoint.armed) Serial.println(F("Commands: STATUS, STOP"));
      serialLength=0; serialDiscard=false;
    } else if(!serialDiscard) {
      if(serialLength<sizeof(serialCommand)-1) serialCommand[serialLength++]=c;
      else serialDiscard=true;
    }
  }
}

void receiveFrame(int count) {
  i2cSeen=true;
  if(queued==2) { while(Wire.available()) Wire.read(); overflow=true; return; }
  uint8_t n=0;
  while(Wire.available()) { int value=Wire.read(); if(n<32) rx[head][n++]=uint8_t(value); }
  rxLength[head]=count==32?n:0; head=uint8_t((head+1)&1); ++queued;
}
void requestFrame() { i2cSeen=true; Wire.write(snapshots[activeSnapshot],32); }
void publish() {
  flip::Frame f=endpoint.status(millis());
  uint8_t next=uint8_t(activeSnapshot^1); memcpy(snapshots[next],f.bytes,32);
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { activeSnapshot=next; }
}
void setup() {
  PORTB &= 0xf0; DDRB |= 0x0f;
  Serial.begin(115200);
  Serial.println(F("FlipClock UNO 0.2.0 protocol=1 BOOT_UNARMED; STATUS / STOP"));
  publish(); memcpy(snapshots[activeSnapshot^1],snapshots[activeSnapshot],32);
  Wire.begin(0x12); Wire.onReceive(receiveFrame); Wire.onRequest(requestFrame);
  wdt_enable(WDTO_2S);
}
void loop() {
  if(i2cSeen && !bench.masterSeen) bench.masterActivity(endpoint);
  serviceSerial();
  if(i2cSeen && bench.enabled) bench.masterActivity(endpoint);
  flip::Frame frames[2]; uint8_t lengths[2],n=0; bool over=false;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    over=overflow; overflow=false;
    while(queued && n<2) {
      lengths[n]=rxLength[tail];
      for(uint8_t i=0;i<32;++i) frames[n].bytes[i]=rx[tail][i];
      tail=uint8_t((tail+1)&1); --queued; ++n;
    }
  }
  if(over) endpoint.fail(flip::RX_OVERFLOW);
  // Handle only CRC-valid STOP first; older queued MOVE becomes stale.
  int8_t stop=-1;
  for(uint8_t i=0;i<n;++i) if(lengths[i]==32 && frames[i].valid() && frames[i].op()==flip::STOP) stop=int8_t(i);
  if(stop>=0) endpoint.handle(frames[stop],millis());
  for(uint8_t i=0;i<n;++i) if(int8_t(i)!=stop) {
    if(lengths[i]==32) endpoint.handle(frames[i],millis()); else ++endpoint.badFrames;
  }
  endpoint.tick(millis(),micros());
  PORTB=uint8_t((PORTB&0xf0)|(endpoint.mask&15));
  publish(); wdt_reset();
}
