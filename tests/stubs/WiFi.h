#pragma once
#include "Arduino.h"
constexpr int WL_CONNECTED=3,WIFI_STA=1,WIFI_AP_STA=3;
struct FakeWifi {
  int state=0; std::string apName,apPassword;
  int status() { return state; } void persistent(bool) {} void mode(int) {} void begin(const char*,const char*) {}
  bool softAP(const char* name,const char* password) { apName=name; apPassword=password; return true; }
}; inline FakeWifi WiFi;
inline void configTime(int,int,const char*,const char*,const char*) {}
