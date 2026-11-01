// Test adapters only. Production firmware compiles against the official board core.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include <string>
#include <vector>
#include <deque>
#include <map>
#include <FlipCalendar.h>
#define PROGMEM
inline uint32_t fakeMs=0;
inline uint64_t fakeUs=0;
// A single one-shot esp_timer that fires while simulated time passes, at its exact microsecond.
constexpr int ESP_OK=0,ESP_ERR_INVALID_STATE=259;
using esp_err_t=int;
struct esp_timer_create_args_t { void (*callback)(void*); void* arg; const char* name; };
struct FakeTimer { void (*callback)(void*)=nullptr; void* arg=nullptr; uint64_t due=0; bool armed=false; };
using esp_timer_handle_t=FakeTimer*;
inline FakeTimer fakeTimer;
inline esp_err_t esp_timer_create(const esp_timer_create_args_t* a,esp_timer_handle_t* out) { fakeTimer.callback=a->callback; fakeTimer.arg=a->arg; *out=&fakeTimer; return ESP_OK; }
inline esp_err_t esp_timer_start_once(esp_timer_handle_t t,uint64_t us) { if(t->armed) return ESP_ERR_INVALID_STATE; t->due=fakeUs+us; t->armed=true; return ESP_OK; }
inline esp_err_t esp_timer_stop(esp_timer_handle_t t) { if(!t->armed) return ESP_ERR_INVALID_STATE; t->armed=false; return ESP_OK; }
struct portMUX_TYPE { int unused; };
#define portMUX_INITIALIZER_UNLOCKED {0}
#define portENTER_CRITICAL(m) (void)(m)
#define portEXIT_CRITICAL(m) (void)(m)
constexpr uint8_t LOW=0,HIGH=1,OUTPUT=3;
inline uint8_t fakePins[40]={}; inline uint8_t fakePinModes[40]={};
inline void pinMode(uint8_t pin,uint8_t mode) { fakePinModes[pin]=mode; }
inline void digitalWrite(uint8_t pin,uint8_t value) { fakePins[pin]=value; }
inline uint32_t millis() { return fakeMs; }
inline uint32_t micros() { return uint32_t(fakeUs); }
inline void delay(uint32_t ms) {
  for(uint32_t i=0;i<ms;++i) {
    ++fakeMs; uint64_t end=uint64_t(fakeMs)*1000;
    while(fakeTimer.armed && fakeTimer.due<=end) { fakeUs=fakeTimer.due; fakeTimer.armed=false; fakeTimer.callback(fakeTimer.arg); }
    fakeUs=end;
  }
}
inline uint32_t esp_random() { static uint32_t value=123456; value=value*1664525UL+1013904223UL; return value; }
inline int esp_reset_reason() { return 1; }
inline size_t strlcpy(char* out,const char* in,size_t n) { size_t len=strlen(in); if(n) { size_t k=len<n-1?len:n-1; memcpy(out,in,k); out[k]=0; } return len; }
struct FakeESP { bool restarted=false; uint64_t getEfuseMac() { return 0x123456789abcULL; } void restart() { restarted=true; } }; inline FakeESP ESP;
struct FakeSerial {
  std::string output,input;
  void begin(int) {} int available() { return int(input.size()); }
  int read() { int c=uint8_t(input[0]); input.erase(0,1); return c; }
  void print(const char* s) { output+=s; }
  void println(const char* s) { output+=s; output+='\n'; }
  void printf(const char* fmt,...) { char b[2048]; va_list ap; va_start(ap,fmt); vsnprintf(b,sizeof(b),fmt,ap); va_end(ap); output+=b; }
}; inline FakeSerial Serial;
struct FakeQueue { size_t cap,size; std::deque<std::vector<uint8_t>> items; };
using QueueHandle_t=FakeQueue*;
constexpr int pdTRUE=1;
inline QueueHandle_t xQueueCreate(size_t cap,size_t size) { return new FakeQueue{cap,size,{}}; }
inline int xQueueSend(QueueHandle_t q,const void* p,int) {
  if(q->items.size()>=q->cap) return 0;
  q->items.emplace_back((const uint8_t*)p,(const uint8_t*)p+q->size); return pdTRUE;
}
inline int xQueueReceive(QueueHandle_t q,void* p,int) { if(q->items.empty()) return 0; memcpy(p,q->items.front().data(),q->size); q->items.pop_front(); return pdTRUE; }
inline int xQueueOverwrite(QueueHandle_t q,const void* p) { q->items.clear(); return xQueueSend(q,p,0); }
inline void xQueueReset(QueueHandle_t q) { q->items.clear(); }
