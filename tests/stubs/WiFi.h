#pragma once
#include "Arduino.h"
constexpr int WL_NO_SSID_AVAIL=1,WL_CONNECTED=3,WL_CONNECT_FAILED=4,WL_DISCONNECTED=6,WIFI_STA=1,WIFI_AP_STA=3;
using WiFiEvent_t=int; constexpr int ARDUINO_EVENT_WIFI_STA_DISCONNECTED=1;
struct WiFiEventInfo_t { struct { int reason; } wifi_sta_disconnected; };
constexpr int WIFI_SCAN_RUNNING=-1,WIFI_SCAN_FAILED=-2,WIFI_AUTH_OPEN=0,WIFI_AUTH_WPA2_PSK=3;
// Test adapter: a scripted radio. `state` is what WiFi.status() reports; scans complete after `scanPolls` polls.
struct FakeNet { std::string ssid; int rssi; int auth; };
struct FakeIp { std::string toString() const { return "192.168.1.77"; } };
struct FakeWifi {
  int state=WL_DISCONNECTED; std::string apName,apPassword,beganSsid,beganPassword; bool disconnected=false;
  std::vector<FakeNet> nets; int scanPolls=0,scanCalls=0; bool scanning=false;
  void (*eventCb)(WiFiEvent_t,WiFiEventInfo_t)=nullptr; int begins=0;
  void onEvent(void (*cb)(WiFiEvent_t,WiFiEventInfo_t),int) { eventCb=cb; }
  void fireDisconnect(int reason) { WiFiEventInfo_t info; info.wifi_sta_disconnected.reason=reason; eventCb(ARDUINO_EVENT_WIFI_STA_DISCONNECTED,info); }
  int status() { return state; } void persistent(bool) {} void mode(int) {}
  void begin(const char* ssid,const char* password) { beganSsid=ssid; beganPassword=password; disconnected=false; ++begins; }
  void disconnect(bool=false,bool=false) { disconnected=true; beganSsid.clear(); state=WL_DISCONNECTED; }
  bool softAP(const char* name,const char* password) { apName=name; apPassword=password; return true; }
  int scanNetworks(bool,bool=false) { ++scanCalls; scanning=true; scanPolls=0; return WIFI_SCAN_RUNNING; }
  int scanComplete() { if(!scanning) return WIFI_SCAN_FAILED; if(failScans>0 && ++scanPolls>=2) { --failScans; scanning=false; return WIFI_SCAN_FAILED; } return ++scanPolls<3?WIFI_SCAN_RUNNING:int(nets.size()); }
  void scanDelete() { scanning=false; }
  std::string SSID(int i) { return nets[i].ssid; } int RSSI(int i) { return nets[i].rssi; } int encryptionType(int i) { return nets[i].auth; }
  int RSSI() { return -52; } FakeIp localIP() { return {}; } FakeIp softAPIP() { return {}; }
  std::string SSID() { return beganSsid; } std::string psk() { return beganPassword; } bool setHostname(const char*) { return true; }
  int failScans=0; // scans that fail outright before one succeeds
}; inline FakeWifi WiFi;
inline void configTime(int,int,const char*,const char*,const char*) {}
