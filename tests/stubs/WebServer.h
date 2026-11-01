#pragma once
#include "Arduino.h"
#include <functional>
enum HTTPMethod { HTTP_GET, HTTP_POST };
enum HTTPUploadStatus { UPLOAD_FILE_START, UPLOAD_FILE_WRITE, UPLOAD_FILE_END, UPLOAD_FILE_ABORTED };
struct HTTPUpload { HTTPUploadStatus status=UPLOAD_FILE_START; uint8_t* buf=nullptr; size_t currentSize=0; };
// Test adapter: routes are invoked directly; the production class is the board core's WebServer.
struct WebServer {
  explicit WebServer(int) {}
  std::map<std::string,std::function<void()>> get,post,uploader;
  std::string body,lastType,lastBody,bearer; int lastCode=0; bool authOk=true,begun=false; HTTPUpload current;
  void on(const char* path,HTTPMethod method,std::function<void()> handler) { (method==HTTP_GET?get:post)[path]=handler; }
  void on(const char* path,HTTPMethod method,std::function<void()> handler,std::function<void()> upload) { on(path,method,handler); uploader[path]=upload; }
  HTTPUpload& upload() { return current; }
  void begin() { begun=true; }
  void handleClient() {}
  std::string header(const char*) { return authOk?bearer:std::string(); }
  std::string arg(const char*) { return body; }
  void sendHeader(const char*,const char*) {}
  void send(int code,const char* type,const char* text) { lastCode=code; lastType=type; lastBody=text; }
  void send_P(int code,const char* type,const char* text) { send(code,type,text); }
};
