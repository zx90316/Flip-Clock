#pragma once
#include "Arduino.h"
#include <functional>
enum HTTPMethod { HTTP_GET, HTTP_POST };
// Test adapter: routes are invoked directly; the production class is the board core's WebServer.
struct WebServer {
  explicit WebServer(int) {}
  std::map<std::string,std::function<void()>> get,post;
  std::string body,lastType,lastBody; int lastCode=0; bool authOk=true,begun=false;
  void on(const char* path,HTTPMethod method,std::function<void()> handler) { (method==HTTP_GET?get:post)[path]=handler; }
  void begin() { begun=true; }
  void handleClient() {}
  bool authenticate(const char*,const char*) { return authOk; }
  void requestAuthentication() { lastCode=401; lastBody.clear(); }
  std::string arg(const char*) { return body; }
  void sendHeader(const char*,const char*) {}
  void send(int code,const char* type,const char* text) { lastCode=code; lastType=type; lastBody=text; }
  void send_P(int code,const char* type,const char* text) { send(code,type,text); }
};
