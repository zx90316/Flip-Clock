#pragma once
#include "Arduino.h"
constexpr int WL_CONNECTED=3,WIFI_STA=1;
struct FakeWifi { int state=0; int status() { return state; } void persistent(bool) {} void mode(int) {} void begin(const char*,const char*) {} }; inline FakeWifi WiFi;
inline void configTime(int,int,const char*,const char*,const char*) {}
