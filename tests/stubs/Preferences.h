#pragma once
#include "Arduino.h"
inline std::map<std::string,std::map<std::string,std::vector<uint8_t>>> fakeNvs;
inline bool nvsWriteFailure=false;
class Preferences {
  std::string space;
 public:
  bool begin(const char* name,bool=false) { space=name; return true; }
  void end() {}
  size_t getBytesLength(const char* key) { return fakeNvs[space][key].size(); }
  size_t getBytes(const char* key,void* out,size_t n) { auto& bytes=fakeNvs[space][key]; if(bytes.size()>n) return 0; memcpy(out,bytes.data(),bytes.size()); return bytes.size(); }
  size_t putBytes(const char* key,const void* p,size_t n) { if(nvsWriteFailure) return 0; fakeNvs[space][key].assign((const uint8_t*)p,(const uint8_t*)p+n); return n; }
  bool remove(const char* key) { return fakeNvs[space].erase(key)>0; }
};
