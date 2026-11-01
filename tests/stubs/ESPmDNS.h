#pragma once
#include "Arduino.h"
struct FakeMdns {
  bool on=false; std::string name;
  bool begin(const char* host) { on=true; name=host; return true; }
  void end() { on=false; }
  void addService(const char*,const char*,int) {}
}; inline FakeMdns MDNS;
