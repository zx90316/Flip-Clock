#pragma once
#include "Arduino.h"
constexpr size_t UPDATE_SIZE_UNKNOWN=0xFFFFFFFFUL;
// Test adapter: records what the production OTA path sends to the Update library.
struct FakeUpdate {
  bool began=false,failBegin=false,failEnd=false,ended=false,aborted=false; std::string data;
  bool begin(size_t) { if(failBegin) return false; began=true; ended=aborted=false; data.clear(); return true; }
  size_t write(uint8_t* d,size_t n) { data.append(reinterpret_cast<const char*>(d),n); return n; }
  bool end(bool) { if(failEnd) return false; ended=true; return true; }
  void abort() { aborted=true; began=false; }
}; inline FakeUpdate Update;
