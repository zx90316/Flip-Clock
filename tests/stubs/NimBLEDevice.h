#pragma once
#include "Arduino.h"
constexpr uint16_t BLE_HS_CONN_HANDLE_NONE=0xffff;
constexpr int BLE_HS_EDONE=14,BLE_HS_IO_DISPLAY_ONLY=0;
namespace NIMBLE_PROPERTY { constexpr int WRITE=1,WRITE_ENC=2,WRITE_AUTHEN=4,INDICATE=8,READ_ENC=16,READ_AUTHEN=32,READ=64; }
struct NimBLEAddress {};
struct NimBLEConnInfo {
  bool encrypted=true,auth=true,bond=true; uint16_t handle=1;
  bool isEncrypted() { return encrypted; } bool isAuthenticated() { return auth; } bool isBonded() { return bond; }
  uint8_t getSecKeySize() { return 16; }
  uint16_t getConnHandle() { return handle; } NimBLEAddress getIdAddress() { return {}; }
};
class NimBLECharacteristic; class NimBLEServer;
class NimBLECharacteristicCallbacks {
 public:
  virtual ~NimBLECharacteristicCallbacks()=default;
  virtual void onWrite(NimBLECharacteristic*,NimBLEConnInfo&) {}
  virtual void onSubscribe(NimBLECharacteristic*,NimBLEConnInfo&,uint16_t) {}
  virtual void onStatus(NimBLECharacteristic*,NimBLEConnInfo&,int) {}
};
class NimBLEServerCallbacks {
 public:
  virtual ~NimBLEServerCallbacks()=default;
  virtual void onConnect(NimBLEServer*,NimBLEConnInfo&) {}
  virtual void onDisconnect(NimBLEServer*,NimBLEConnInfo&,int) {}
  virtual uint32_t onPassKeyDisplay() { return 0; }
  virtual void onAuthenticationComplete(NimBLEConnInfo&) {}
};
inline std::string fakeIndications;
class NimBLECharacteristic {
 public:
  std::string value; NimBLECharacteristicCallbacks* cb=nullptr;
  std::string getValue() { return value; } void setValue(const char* v) { value=v; }
  void setCallbacks(NimBLECharacteristicCallbacks* c) { cb=c; }
  bool indicate(const uint8_t* p,size_t n,uint16_t) { fakeIndications.append((const char*)p,n); NimBLEConnInfo i; if(cb) cb->onStatus(this,i,BLE_HS_EDONE); return true; }
};
class NimBLEService { public: NimBLECharacteristic* createCharacteristic(const char*,int,int) { return new NimBLECharacteristic; } void start() {} };
class NimBLEServer {
 public:
  void start() {}
  NimBLEServerCallbacks* cb=nullptr;
  void disconnect(uint16_t h) { NimBLEConnInfo i; i.handle=h; if(cb) cb->onDisconnect(this,i,0); }
  void setCallbacks(NimBLEServerCallbacks* c) { cb=c; }
  NimBLEService* createService(const char*) { return new NimBLEService; }
};
class FakeAdv { public: bool on=false; void start() { on=true; } void stop() { on=false; } void addServiceUUID(const char*) {} void setName(const char*) {} void enableScanResponse(bool) {} };
class NimBLEDevice {
 public:
  static void init(const char*) {} static void setSecurityAuth(bool,bool,bool) {} static void setSecurityIOCap(int) {}
  static void setSecurityPasskey(uint32_t) {} static NimBLEServer* createServer() { return new NimBLEServer; }
  static bool isBonded(NimBLEAddress) { return true; } static bool deleteAllBonds() { return true; }
  static FakeAdv* getAdvertising() { static FakeAdv adv; return &adv; }
};
