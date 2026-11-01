// SPDX-License-Identifier: GPL-3.0-only
#include "app.h"
#include "services.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Update.h>
#include <NimBLEDevice.h>
#include <ESPmDNS.h>
#include <esp_sntp.h>
#include <esp_system.h>
#include <cJSON.h>
#include <FlipStream.h>
#include "web_page.h"
#define HOSTNAME "flipclock"
#include <atomic>
#include <string>
#include <math.h>

namespace clockapp {
static const uint32_t CHUNK_STEPS=9000; // below the Uno's 10000-step move limit
static const char* SERVICE="b50c1000-7e6b-4e67-a540-a06c4fe1b201";
static const char* RX="b50c1001-7e6b-4e67-a540-a06c4fe1b201";
static const char* TX="b50c1002-7e6b-4e67-a540-a06c4fe1b201";
static const char* INFO="b50c1003-7e6b-4e67-a540-a06c4fe1b201";
Planner planner; Store store; NetClock rtc; Link link;
Lines bleLines,uartLines; Requests requests;
NimBLEServer* server=nullptr; NimBLECharacteristic* eventTx=nullptr;
std::atomic<uint16_t> peer{BLE_HS_CONN_HANDLE_NONE};
std::atomic<bool> authenticated{false},subscribed{false},disconnected{false};
std::atomic<uint32_t> connectionEpoch{0},pairUntil{0},passkey{0};
std::atomic<int> indicationAck{0};
struct Chunk { uint32_t epoch; uint16_t length; uint8_t bytes[512]; };
struct Reply { uint32_t epoch; char text[1537]; };
QueueHandle_t rxQueue,txQueue,syncQueue;
char bootId[9],lastError[40]="",source[16]="invalid";
bool systemFault=false,lastLinkReady=false,largeRequired=false;
bool autoWasEnabled=true;
uint32_t lastRtc=0,lastRtcGoodMs=0,lastSettle=0,lastCheckpoint=0;
uint32_t jobSeq=0,nextR=0,jobRequest=0,armSeq=0,saveRequest=0;
bool jobBle=false,saveBle=false,jobJog=false,savePending=false,saveWasPaused=true;
uint32_t saveRevision=0; // planner revision when a background save began; any later change keeps the clock paused
int32_t jobSteps=0;
uint16_t manualPages=0,jobPages=1; // jobPages: pages covered by the move in flight (one continuous move may span several)
uint16_t manualRequested_=0,manualCompleted_=0;
uint32_t manualRequest=0; bool manualBle=false;
int64_t observedUtc=0,pendingSync=0,lastSync=0,lastOffset=0;
uint32_t observedMs=0;
struct Network { char ssid[33]={},password[65]={}; char hosts[3][64]={"pool.ntp.org","time.cloudflare.com","time.google.com"}; } network;
uint32_t lastWifi=0,wifiBackoff=30000,pendingSyncMs=0;
bool sntpStarted=false;
uint32_t stopRequest_=0,pauseRequest_=0,clearRequest_=0,queuedJogRequest_=0,clearSent_=0;
bool stopBle_=false,pauseBle_=false,clearBle_=false,queuedJogBle_=false,largeConfirmed_=false,pendingSyncConfirm_=false;
int32_t queuedJog_=0;
std::atomic<bool> rxOverflow_{false};
// Web console: replies of one command are captured; late completions still go to UART.
WebServer web(80); std::string* webOut=nullptr; uint32_t webSeq=0;
char webPassword[13]="",apName[24]="";
bool saveNetwork(); void wifiGet(); void wifiPost(); void wifiTick(uint32_t now); // defined with the other network code
bool syncResume=false; // an NTP correction paused a running clock: resume by itself if the correction is small
// Boot restore: the committed snapshot is trusted only after the commissioning wizard saved it.
bool restoreActive=false,restoredFromSnapshot=false; int32_t savedDisplay=-1; uint32_t savedRemainder=0;

bool pairOpen() { uint32_t end=pairUntil.load(); return end && int32_t(end-millis())>0; }
void errorState(const char* code,bool position=true) {
  strlcpy(lastError,code,sizeof(lastError)); systemFault=true; planner.paused=true;
  if(position) planner.invalidate();
}
void output(const char* text,bool ble) {
  if(!ble) { if(webOut) webOut->append(text); else Serial.print(text); return; }
  if(!authenticated.load() || !subscribed.load()) return;
  Reply reply; reply.epoch=connectionEpoch.load(); strlcpy(reply.text,text,sizeof(reply.text));
  if(xQueueSend(txQueue,&reply,0)!=pdTRUE) {
    // Missing application results must never authorize another mechanical job.
    planner.paused=true; strlcpy(lastError,"E_TX_BACKPRESSURE",sizeof(lastError));
    uint16_t handle=peer.load(); if(handle!=BLE_HS_CONN_HANDLE_NONE) server->disconnect(handle);
  }
}
void respond(uint32_t id,const char* phase,const char* extra,bool ble) {
  char data[513]; snprintf(data,sizeof(data),"{\"v\":1,\"id\":%lu,\"boot_id\":\"%s\",\"phase\":\"%s\"%s}\n",
    (unsigned long)id,bootId,phase,extra?extra:"");
  for(auto& e:requests.entries) if(e.id==id) { strlcpy(e.response,data,sizeof(e.response)); break; }
  output(data,ble);
}
void reject(uint32_t id,const char* code,bool ble) {
  char extra[100]; snprintf(extra,sizeof(extra),",\"code\":\"%s\"",code); respond(id,"error",extra,ble);
}
bool safeIdle() { return !jobSeq && !queuedJog_ && !manualPages && !savePending && !link.pending && !link.running(); }
bool number(cJSON* root,const char* key,int64_t lo,int64_t hi,int64_t& value) {
  cJSON* p=cJSON_GetObjectItemCaseSensitive(root,key);
  if(!cJSON_IsNumber(p) || !isfinite(p->valuedouble) || floor(p->valuedouble)!=p->valuedouble ||
      p->valuedouble<double(lo) || p->valuedouble>double(hi)) return false;
  value=int64_t(p->valuedouble); return true;
}
bool boolean(cJSON* root,const char* key,bool& value) {
  cJSON* p=cJSON_GetObjectItemCaseSensitive(root,key); if(!cJSON_IsBool(p)) return false;
  value=cJSON_IsTrue(p); return true;
}
const char* stateName() {
  return systemFault?"FAULT":!link.ready?"LINK_WAIT":!rtc.valid?"NEEDS_TIME":
    !planner.config.mechanics || !planner.position?"NEEDS_CALIBRATION":jobSeq?"MOVING":
    largeRequired?"NEEDS_CATCHUP_CONFIRM":planner.paused?"PAUSED":"IDLE";
}
void status(uint32_t id,bool ble) {
  const char* state=stateName();
  char all[1537],one[513],two[513],three[513];
  snprintf(one,sizeof(one),"{\"v\":1,\"id\":%lu,\"part\":1,\"parts\":3,\"phase\":\"completed\",\"state\":\"%s\",\"boot_id\":\"%s\",\"rtc_utc_s\":%lld,\"time_valid\":%s,\"utc_offset_min\":%d,\"display_index\":%u,\"position_confidence\":\"%s\",\"fractional_remainder\":%lu,\"moving\":%s,\"job_id\":%lu,\"remaining_steps\":%lu}\n",
    (unsigned long)id,state,bootId,(long long)rtc.utc,rtc.valid?"true":"false",planner.config.offset,
    planner.display,planner.position?(planner.committed?"open_loop":"user_confirmed"):"unknown",
    (unsigned long)planner.remainder,jobSeq?"true":"false",(unsigned long)jobSeq,(unsigned long)link.status.arg(1));
  snprintf(two,sizeof(two),"{\"v\":1,\"id\":%lu,\"part\":2,\"parts\":3,\"phase\":\"completed\",\"config_generation\":%lu,\"config_dirty\":%s,\"reset_reason\":%d,\"last_error\":\"%s\",\"coil_outputs_zero\":%s,\"i2c_error_count\":%lu,\"time_source\":\"%s\",\"last_sync_utc\":%lld,\"last_sync_offset_s\":%lld,\"wifi_state\":\"%s\",\"auto_time\":%s,\"pending_sync_utc\":%lld,\"nvs_write_count\":%lu}\n",
    (unsigned long)id,(unsigned long)store.saved.generation,store.dirty?"true":"false",int(esp_reset_reason()),lastError,
    link.coilZero()?"true":"false",(unsigned long)(link.errors+rtc.errors),rtc.valid?source:"invalid",(long long)lastSync,
    (long long)lastOffset,WiFi.status()==WL_CONNECTED?"connected":"offline",planner.config.autoTime?"true":"false",
    (long long)pendingSync,(unsigned long)store.writes);
  snprintf(three,sizeof(three),"{\"v\":1,\"id\":%lu,\"part\":3,\"parts\":3,\"phase\":\"completed\",\"snapshot_valid\":%s,\"snapshot_utc\":%lld,\"snapshot_display_index\":%u,\"snapshot_remainder\":%lu,\"snapshot_phase\":%u,\"snapshot_generation\":%lu,\"mechanics_confirmed\":%s,\"uno_session\":%lu,\"uno_state\":%u,\"uno_error\":%u,\"firmware\":\"0.3.0\",\"protocol\":1}\n",
    (unsigned long)id,store.saved.hasSnapshot?"true":"false",(long long)store.saved.utc,store.saved.display,
    (unsigned long)store.saved.r,store.saved.phase,(unsigned long)store.saved.snapshotGeneration,planner.config.mechanics?"true":"false",
    (unsigned long)link.status.session(),link.status.op(),unsigned(get16(link.status.bytes+28)&255));
  snprintf(all,sizeof(all),"%s%s%s",one,two,three);
  for(auto& e:requests.entries) if(e.id==id) { strlcpy(e.response,all,sizeof(e.response)); break; }
  output(all,ble);
}
void configReply(uint32_t id,bool ble) {
  char extra[420]; const Config& c=planner.config;
  snprintf(extra,sizeof(extra),",\"steps_per_page_u6\":%llu,\"cycle_minutes\":%u,\"mechanics_confirmed\":%s,\"max_step_rate\":%u,\"acceleration\":%u,\"settle_ms\":%u,\"utc_offset_min\":%d,\"max_auto_catchup_pages\":%u,\"max_catchup_seconds\":%u,\"allow_reverse\":%s,\"forward_direction\":%d,\"auto_time\":%s,\"checkpoint_interval_min\":%u,\"config_generation\":%lu,\"config_dirty\":%s",
    (unsigned long long)c.q,c.cycle,c.mechanics?"true":"false",c.rate,c.accel,c.settle,c.offset,c.maxPages,c.maxSeconds,
    c.reverse?"true":"false",c.direction,c.autoTime?"true":"false",c.checkpoint,(unsigned long)store.saved.generation,store.dirty?"true":"false");
  respond(id,"completed",extra,ble);
}
bool applyConfig(cJSON* values) {
  if(!cJSON_IsObject(values)) return false;
  Config c=planner.config;
  for(cJSON* p=values->child;p;p=p->next) {
    if(!p->string) return false;
    const char* k=p->string; int64_t v; bool b;
    if(!strcmp(k,"mechanics_confirmed") || !strcmp(k,"allow_reverse") || !strcmp(k,"auto_time")) {
      if(!boolean(values,k,b)) return false;
      if(!strcmp(k,"mechanics_confirmed")) c.mechanics=b;
      if(!strcmp(k,"allow_reverse")) { if(b) return false; c.reverse=false; } // v1 build disables reverse on both boards.
      if(!strcmp(k,"auto_time")) c.autoTime=b;
      continue;
    }
    if(!number(values,k,-720,10000000000LL,v)) return false;
    if(!strcmp(k,"steps_per_page_u6")) { if(v<D || v>10000LL*D) return false; c.q=uint64_t(v); }
    else if(!strcmp(k,"cycle_minutes")) { if(v!=720 && v!=1440) return false; c.cycle=uint16_t(v); }
    else if(!strcmp(k,"max_step_rate")) { if(v<10 || v>MAX_RATE) return false; c.rate=uint16_t(v); }
    else if(!strcmp(k,"acceleration")) { if(v<1 || v>MAX_ACCEL) return false; c.accel=uint16_t(v); }
    else if(!strcmp(k,"settle_ms")) { if(v<0 || v>5000) return false; c.settle=uint16_t(v); }
    else if(!strcmp(k,"utc_offset_min")) { if(v< -720 || v>840) return false; c.offset=int16_t(v); }
    else if(!strcmp(k,"max_auto_catchup_pages")) { if(v<1 || v>60) return false; c.maxPages=uint16_t(v); }
    else if(!strcmp(k,"max_catchup_seconds")) { if(v<1 || v>120) return false; c.maxSeconds=uint16_t(v); }
    else if(!strcmp(k,"checkpoint_interval_min")) { if(v<0 || v>1440) return false; c.checkpoint=uint16_t(v); }
    else if(!strcmp(k,"forward_direction")) { if(v!=1) return false; c.direction=1; }
    else return false;
  }
  if(!c.valid()) return false;
  bool geometry=c.q!=planner.config.q || c.cycle!=planner.config.cycle || c.direction!=planner.config.direction || !c.mechanics;
  planner.config=c; planner.changed(geometry); store.dirty=true; largeRequired=false;
  return true;
}
// Motion timeout for one move: the planner's bound plus 50% and 5 s for loop jitter on the Uno at high rates.
uint32_t moveTimeoutMs(uint32_t steps) { uint32_t e=estimateMs(steps,planner.config); return e+e/2+5000; }
bool startJob(bool jog,int32_t steps,uint32_t request,bool ble) {
  if(!link.ready || link.fault || !link.armed() || link.pending || jobSeq) return false;
  uint32_t timeout=moveTimeoutMs(magnitude(steps));
  if(timeout>120000UL) return false;
  if(!link.send(MOVE,uint32_t(steps),planner.config.rate,planner.config.accel,timeout)) return false;
  jobSeq=link.seq; jobSteps=steps; jobJog=jog; jobRequest=request; jobBle=ble;
  if(jog) planner.invalidate();
  return true;
}
void cancelJob(const char* code) {
  if(jobRequest) reject(jobRequest,code,jobBle);
  if(manualRequest && manualRequest!=jobRequest) reject(manualRequest,code,manualBle);
  jobSeq=jobRequest=manualRequest=0; manualPages=0; jobPages=1; planner.invalidate();
}
void process(const char* line,bool ble,bool dedupe=true) {
  cJSON* root=cJSON_ParseWithOpts(line,nullptr,true);
  if(!root || !cJSON_IsObject(root)) { cJSON_Delete(root); reject(0,"E_JSON",ble); return; }
  int64_t version=0,request=0; cJSON* boot=cJSON_GetObjectItemCaseSensitive(root,"boot_id");
  cJSON* operation=cJSON_GetObjectItemCaseSensitive(root,"op");
  if(!number(root,"v",1,1,version) || !number(root,"id",1,0xffffffffLL,request) || !cJSON_IsString(operation)) {
    cJSON_Delete(root); reject(0,"E_VERSION",ble); return;
  }
  uint32_t id=uint32_t(request);
  if(!cJSON_IsString(boot) || strcmp(boot->valuestring,bootId)) { cJSON_Delete(root); reject(id,"E_BOOT_CHANGED",ble); return; }
  Requests::Entry* entry=nullptr; Requests::Result result=dedupe?requests.check(id,line,entry):Requests::NEW;
  if(result!=Requests::NEW) {
    if(result==Requests::REPLAY) output(entry->response,ble);
    else {
      // An invalid replay must not overwrite the original cached transaction result.
      char data[150]; snprintf(data,sizeof(data),"{\"v\":1,\"id\":%lu,\"phase\":\"error\",\"code\":\"%s\"}\n",
        (unsigned long)id,result==Requests::REUSE?"E_ID_REUSE":"E_STALE_ID"); output(data,ble);
    }
    cJSON_Delete(root); return;
  }
  const char* op=operation->valuestring;
  // Any deliberate operator action replaces the pending automatic restore.
  if(strcmp(op,"get_status") && strcmp(op,"get_config") && strcmp(op,"set_time") && strcmp(op,"confirm_time") && strcmp(op,"save_config")) restoreActive=false;
  if(!strcmp(op,"get_status")) status(id,ble);
  else if(!strcmp(op,"get_config")) configReply(id,ble);
  else if(!strcmp(op,"stop")) {
    cancelJob("E_STOPPED"); planner.paused=true; saveWasPaused=true; armSeq=0;
    if(queuedJog_) { reject(queuedJogRequest_,"E_STOPPED",queuedJogBle_); queuedJog_=0; }
    if(savePending) { if(saveRequest) reject(saveRequest,"E_STOPPED",saveBle); savePending=false; }
    if(!link.stop()) reject(id,"E_I2C",ble);
    else { respond(id,"accepted",nullptr,ble); stopRequest_=id; stopBle_=ble; }
  }
  else if(!strcmp(op,"pause")) {
    planner.paused=true; saveWasPaused=true; manualPages=0;
    if(queuedJog_) { reject(queuedJogRequest_,"E_STOPPED",queuedJogBle_); queuedJog_=0; }
    if(manualRequest && !jobSeq) { respond(manualRequest,"completed",",\"paused\":true",manualBle); manualRequest=0; }
    respond(id,"accepted",nullptr,ble);
    pauseRequest_=id; pauseBle_=ble;
  }
  else if(!strcmp(op,"clear_fault")) {
    if(jobSeq || savePending) reject(id,"E_BUSY",ble);
    else if(store.fault) reject(id,"E_NVS",ble);
    else {
      planner.invalidate(); systemFault=false; lastError[0]=0; armSeq=0;
      if(link.fault) link.retry();
      clearRequest_=id; clearBle_=ble; respond(id,"accepted",nullptr,ble);
    }
  }
  else if(systemFault || store.fault) reject(id,"E_FAULT",ble);
  else if(!safeIdle() || !planner.paused) reject(id,"E_BUSY",ble);
  else if(!strcmp(op,"set_time")) {
    int64_t utc;
    if(!number(root,"utc_s",946684800LL,4102444799LL,utc)) reject(id,"E_RANGE",ble);
    else if(link.armed()) reject(id,"E_BUSY",ble);
    else if(!rtc.write(utc,millis())) { errorState("E_RTC_WRITE",false); reject(id,"E_I2C",ble); }
    else {
      planner.changed(false); pendingSync=0;
      observedUtc=rtc.utc; observedMs=millis(); strlcpy(source,"ble_manual",sizeof(source));
      char extra[70]; snprintf(extra,sizeof(extra),",\"utc_s\":%lld",(long long)rtc.utc); respond(id,"completed",extra,ble);
    }
  }
  else if(!strcmp(op,"set_config")) {
    if(!applyConfig(cJSON_GetObjectItemCaseSensitive(root,"values"))) reject(id,"E_RANGE",ble);
    else respond(id,"completed",",\"config_dirty\":true",ble);
  }
  else if(!strcmp(op,"save_config")) {
    savePending=true; saveRequest=id; saveBle=ble; saveWasPaused=true; respond(id,"accepted",nullptr,ble);
  }
  else if(!strcmp(op,"set_display")) {
    int64_t hour,minute; bool aligned=false;
    if(!number(root,"hour",0,23,hour) || !number(root,"minute",0,59,minute) || !boolean(root,"aligned",aligned) || !aligned || !planner.config.mechanics)
      reject(id,"E_RANGE",ble);
    else { planner.setDisplay(uint16_t((hour*60+minute)%planner.config.cycle)); largeRequired=false; respond(id,"completed",nullptr,ble); }
  }
  else if(!strcmp(op,"preview_sync")) {
    if(!rtc.valid) reject(id,"E_TIME_INVALID",ble);
    else if(!planner.makePreview(rtc.utc,millis(),esp_random())) reject(id,"E_NOT_CALIBRATED",ble);
    else {
      const Preview& p=planner.preview; char extra[200];
      snprintf(extra,sizeof(extra),",\"plan_id\":%lu,\"pages\":%u,\"target_index\":%u,\"estimated_ms\":%lu,\"config_revision\":%lu,\"requires_confirmation\":%s",
        (unsigned long)p.id,p.pages,target(rtc.utc,planner.config),(unsigned long)p.estimate,(unsigned long)planner.revision,p.large?"true":"false");
      respond(id,"completed",extra,ble);
    }
  }
  else if(!strcmp(op,"resume")) {
    int64_t plan; bool confirm=false;
    if(!number(root,"plan_id",1,0xffffffffLL,plan) || (cJSON_HasObjectItem(root,"confirm_large") && !boolean(root,"confirm_large",confirm))) reject(id,"E_RANGE",ble);
    else if(!rtc.valid) reject(id,"E_TIME_INVALID",ble);
    else if(!link.ready) reject(id,"E_I2C",ble);
    else if(!planner.resume(uint32_t(plan),confirm,rtc.utc,millis())) reject(id,"E_PLAN_STALE",ble);
    else { largeRequired=false; largeConfirmed_=confirm; respond(id,"completed",nullptr,ble); }
  }
  else if(!strcmp(op,"jog_steps")) {
    int64_t steps;
    if(!number(root,"steps",-8000,8000,steps) || !steps) reject(id,"E_RANGE",ble);
    else if(steps<0) reject(id,"E_REVERSE_DISABLED",ble);
    else if(!link.ready) reject(id,"E_I2C",ble);
    else { queuedJog_=int32_t(steps); queuedJogRequest_=id; queuedJogBle_=ble; respond(id,"accepted",nullptr,ble); }
  }
  else if(!strcmp(op,"advance_pages")) {
    int64_t pages;
    if(!number(root,"pages",1,720,pages)) reject(id,"E_RANGE",ble);
    else if(!planner.position || !planner.config.mechanics) reject(id,"E_NOT_CALIBRATED",ble);
    else if(!link.ready) reject(id,"E_I2C",ble);
    else { manualPages=uint16_t(pages); manualRequested_=manualPages; manualCompleted_=0; manualRequest=id; manualBle=ble; respond(id,"accepted",nullptr,ble); }
  }
  else if(!strcmp(op,"confirm_time")) {
    int64_t expected;
    if(!number(root,"utc_s",946684800LL,4102444799LL,expected) || expected!=pendingSync || !pendingSync || uint32_t(millis()-pendingSyncMs)>120000)
      reject(id,"E_PLAN_STALE",ble);
    else if(link.armed()) reject(id,"E_BUSY",ble);
    else {
      int64_t value=pendingSync+uint32_t(millis()-pendingSyncMs)/1000;
      if(!rtc.write(value,millis())) { errorState("E_RTC_WRITE",false); reject(id,"E_I2C",ble); }
      else { lastOffset=value-observedUtc; lastSync=value; pendingSync=0; planner.changed(false); observedUtc=rtc.utc; observedMs=millis(); strlcpy(source,"sntp",sizeof(source)); respond(id,"completed",nullptr,ble); }
    }
  }
  else reject(id,"E_OP",ble);
  cJSON_Delete(root);
}

// Position is restored only from a snapshot saved after the commissioning wizard confirmed the mechanics.
bool restoreSnapshot() {
  const Saved& s=store.saved;
  if(store.fault || !s.hasSnapshot || !s.config.mechanics || !planner.config.mechanics || s.snapshotCycle!=planner.config.cycle) return false;
  planner.setDisplay(s.display); planner.remainder=s.r; savedDisplay=s.display; savedRemainder=s.r;
  restoreActive=true; restoredFromSnapshot=true; return true;
}
const char* tf(bool v) { return v?"true":"false"; }
void buildState(std::string& out) {
  char b[900]; const Saved& s=store.saved;
  snprintf(b,sizeof(b),"{\"fw\":\"0.3.0\",\"state\":\"%s\",\"link\":%s,\"rtc\":%s,\"utc\":%lld,\"off\":%d,\"display\":%u,\"cycle\":%u,\"pos\":%s,\"mech\":%s,\"q\":%llu,\"paused\":%s,\"busy\":%s,\"fault\":%s,\"err\":\"%s\",\"snap\":%s,\"snapDisplay\":%u,\"gen\":%lu,\"dirty\":%s,\"restoring\":%s,\"restored\":%s,\"left\":%lu,\"syncAsk\":%s,\"syncUtc\":%lld,\"rate\":%u,\"accel\":%u,\"ntp\":%s}",
    stateName(),tf(link.ready),tf(rtc.valid),(long long)rtc.utc,planner.config.offset,planner.display,planner.config.cycle,
    tf(planner.position),tf(planner.config.mechanics),(unsigned long long)planner.config.q,tf(planner.paused),
    tf(!safeIdle() || link.armed() || jobSeq),tf(systemFault),lastError,tf(s.hasSnapshot),s.display,(unsigned long)s.generation,
    tf(store.dirty),tf(restoreActive),tf(restoredFromSnapshot),(unsigned long)link.status.arg(1),
    tf(pendingSync && pendingSyncConfirm_),(long long)pendingSync,planner.config.rate,planner.config.accel,tf(planner.config.autoTime));
  out=b;
}
// Wraps a browser request in the same protocol frame BLE uses; replies produced synchronously are returned.
bool webCommand(const char* body,std::string& out) {
  out.clear(); cJSON* in=cJSON_Parse(body);
  if(!in || !cJSON_IsObject(in) || !cJSON_IsString(cJSON_GetObjectItemCaseSensitive(in,"op"))) {
    cJSON_Delete(in); out="{\"phase\":\"error\",\"code\":\"E_JSON\"}\n"; return false;
  }
  for(const char* key:{"v","id","boot_id"}) cJSON_DeleteItemFromObjectCaseSensitive(in,key);
  cJSON_AddNumberToObject(in,"v",1); cJSON_AddNumberToObject(in,"id",double(0xF0000000UL+(++webSeq)));
  cJSON_AddStringToObject(in,"boot_id",bootId);
  char* line=cJSON_PrintUnformatted(in); cJSON_Delete(in);
  if(!line) { out="{\"phase\":\"error\",\"code\":\"E_JSON\"}\n"; return false; }
  webOut=&out; process(line,false,false); webOut=nullptr; cJSON_free(line);
  if(out.empty()) out="{\"phase\":\"error\",\"code\":\"E_NO_REPLY\"}\n";
  return true;
}
void loadWebPassword() {
  static const char alphabet[]="abcdefghjkmnpqrstuvwxyz23456789";
  Preferences p; bool open=p.begin("flip-web",false);
  if(open && p.getBytesLength("pw")==sizeof(webPassword) && p.getBytes("pw",webPassword,sizeof(webPassword))==sizeof(webPassword) &&
     webPassword[12]==0 && strlen(webPassword)==12) { p.end(); return; }
  for(int i=0;i<12;++i) webPassword[i]=alphabet[esp_random()%(sizeof(alphabet)-1)];
  webPassword[12]=0;
  if(open) { p.putBytes("pw",webPassword,sizeof(webPassword)); p.end(); } // Random per boot if NVS is unavailable; never an open AP.
}
bool webAuth() { if(web.authenticate("admin",webPassword)) return true; web.requestAuthentication(); return false; }

// OTA: only while the motor is idle and disarmed. The Update library validates the image on end();
// a failed or interrupted upload leaves the running partition untouched.
bool otaActive=false,otaDenied=false,otaOk=false; size_t otaBytes=0; char otaError[24]="";
void otaFail(const char* code) { strlcpy(otaError,code,sizeof(otaError)); if(otaActive) { Update.abort(); otaActive=false; } }
void otaStart() {
  otaError[0]=0; otaBytes=0; otaOk=false; otaDenied=false; otaActive=false;
  if(!web.authenticate("admin",webPassword)) { otaDenied=true; strlcpy(otaError,"E_AUTH",sizeof(otaError)); return; }
  if(!safeIdle() || link.armed() || jobSeq) { strlcpy(otaError,"E_BUSY",sizeof(otaError)); return; }
  planner.paused=true; restoreActive=false;
  if(!Update.begin(UPDATE_SIZE_UNKNOWN)) { strlcpy(otaError,"E_OTA_NO_PARTITION",sizeof(otaError)); return; }
  otaActive=true;
}
void otaWrite(uint8_t* data,size_t length) {
  if(!otaActive || !length) return;
  if(!otaBytes && data[0]!=0xE9) { otaFail("E_OTA_IMAGE"); return; }
  if(Update.write(data,length)!=length) { otaFail("E_OTA_WRITE"); return; }
  otaBytes+=length;
}
void otaEnd() {
  if(!otaActive) return;
  otaActive=false;
  if(otaBytes<65536 || !Update.end(true)) { Update.abort(); strlcpy(otaError,"E_OTA_END",sizeof(otaError)); return; }
  otaOk=true;
}
void otaFinish() {
  if(!webAuth()) return;
  char body[80]; snprintf(body,sizeof(body),"{\"ok\":%s,\"error\":\"%s\",\"bytes\":%lu}",otaOk?"true":"false",otaError,(unsigned long)otaBytes);
  web.sendHeader("Cache-Control","no-store"); web.send(otaOk?200:409,"application/json",body);
  if(otaOk) { delay(500); ESP.restart(); }
  // The loop was blocked while receiving; do not let the stale heartbeat age raise a link fault.
  link.retry(); lastLinkReady=false;
}
void otaUpload() {
  HTTPUpload& up=web.upload();
  if(up.status==UPLOAD_FILE_START) otaStart();
  else if(up.status==UPLOAD_FILE_WRITE) otaWrite(up.buf,up.currentSize);
  else if(up.status==UPLOAD_FILE_END) otaEnd();
  else if(up.status==UPLOAD_FILE_ABORTED) otaFail("E_OTA_ABORTED");
}
void webSetup() {
  loadWebPassword(); WiFi.softAP(apName,webPassword);
  web.on("/api/ota",HTTP_POST,otaFinish,otaUpload);
  web.on("/api/wifi",HTTP_GET,wifiGet); web.on("/api/wifi",HTTP_POST,wifiPost);
  web.on("/",HTTP_GET,[]() { if(webAuth()) web.send_P(200,"text/html; charset=utf-8",WEB_PAGE); });
  web.on("/api/state",HTTP_GET,[]() {
    if(!webAuth()) return; std::string s; buildState(s); web.sendHeader("Cache-Control","no-store"); web.send(200,"application/json",s.c_str());
  });
  web.on("/api/cmd",HTTP_POST,[]() {
    if(!webAuth()) return; std::string out; webCommand(web.arg("plain").c_str(),out); web.sendHeader("Cache-Control","no-store"); web.send(200,"application/json",out.c_str());
  });
  web.begin();
}

class ServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* s,NimBLEConnInfo& info) override {
    if(peer.load()!=BLE_HS_CONN_HANDLE_NONE || (!pairOpen() && !NimBLEDevice::isBonded(info.getIdAddress()))) { s->disconnect(info.getConnHandle()); return; }
    peer=info.getConnHandle(); ++connectionEpoch; authenticated=false; subscribed=false;
  }
  void onDisconnect(NimBLEServer*,NimBLEConnInfo& info,int) override {
    if(info.getConnHandle()!=peer.load()) return;
    peer=BLE_HS_CONN_HANDLE_NONE; authenticated=false; subscribed=false; ++connectionEpoch; disconnected=true;
  }
  uint32_t onPassKeyDisplay() override { return passkey.load(); }
  void onAuthenticationComplete(NimBLEConnInfo& info) override {
    bool ok=info.isEncrypted() && info.isAuthenticated() && info.isBonded() && info.getSecKeySize()==16;
    authenticated=ok; if(!ok) server->disconnect(info.getConnHandle());
  }
};
class RxCallbacks : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic* c,NimBLEConnInfo& info) override {
    if(info.getConnHandle()!=peer.load() || !authenticated.load() || !subscribed.load()) return;
    auto value=c->getValue(); if(value.size()>512) return;
    Chunk packet; packet.epoch=connectionEpoch.load(); packet.length=uint16_t(value.size()); memcpy(packet.bytes,value.data(),value.size());
    if(xQueueSend(rxQueue,&packet,0)!=pdTRUE) { rxOverflow_=true; }
  }
};
class TxCallbacks : public NimBLECharacteristicCallbacks {
  void onSubscribe(NimBLECharacteristic*,NimBLEConnInfo& info,uint16_t value) override {
    if(info.getConnHandle()==peer.load()) subscribed=bool(value&2);
  }
  void onStatus(NimBLECharacteristic*,NimBLEConnInfo&,int code) override { indicationAck=code==BLE_HS_EDONE?1:-1; }
};
ServerCallbacks serverCallbacks; RxCallbacks rxCallbacks; TxCallbacks txCallbacks;

void txTick(uint32_t now) {
  static Reply current; static size_t offset=0,length=0,lastChunk=0;
  static bool waiting=false; static uint32_t started=0;
  if(!authenticated.load() || !subscribed.load() || current.epoch!=connectionEpoch.load()) {
    waiting=false; offset=length=0; indicationAck=0;
  }
  if(waiting) {
    int ack=indicationAck.exchange(0);
    if(ack<0 || uint32_t(now-started)>3000) { server->disconnect(peer.load()); waiting=false; length=offset=0; return; }
    if(!ack) return;
    offset+=lastChunk; waiting=false;
  }
  if(offset>=length) {
    if(xQueueReceive(txQueue,&current,0)!=pdTRUE) return;
    offset=0; length=strlen(current.text);
    if(current.epoch!=connectionEpoch.load() || !authenticated.load() || !subscribed.load()) { length=0; return; }
  }
  lastChunk=length-offset; if(lastChunk>20) lastChunk=20;
  indicationAck=0; waiting=true; started=now;
  if(!eventTx->indicate(reinterpret_cast<const uint8_t*>(current.text+offset),lastChunk,peer.load())) {
    waiting=false; server->disconnect(peer.load());
  }
}

void sntpCallback(struct timeval* tv) { int64_t value=int64_t(tv->tv_sec); xQueueOverwrite(syncQueue,&value); }
void loadNetwork() {
  Preferences p; if(!p.begin("flip-network",true)) return;
  uint8_t data[sizeof(Network)+4];
  if(p.getBytesLength("config")==sizeof(data) && p.getBytes("config",data,sizeof(data))==sizeof(data) &&
     get32(data+sizeof(Network))==crc32(data,sizeof(Network))) {
    Network value; memcpy(&value,data,sizeof(value));
    if(value.ssid[32]==0 && value.password[64]==0 && value.hosts[0][63]==0 && value.hosts[1][63]==0 && value.hosts[2][63]==0) network=value;
  }
  p.end();
}
bool saveNetwork() {
  Preferences p; if(!p.begin("flip-network",false)) return false;
  uint8_t data[sizeof(Network)+4],check[sizeof(data)]; memcpy(data,&network,sizeof(network)); put32(data+sizeof(network),crc32(data,sizeof(network)));
  bool ok=p.putBytes("config",data,sizeof(data))==sizeof(data) && p.getBytes("config",check,sizeof(check))==sizeof(check) && !memcmp(data,check,sizeof(data));
  p.end(); return ok;
}
// ---- Wi-Fi provisioning: scan, trial-connect, and save only after a verified connection ----
struct ScanEntry { char ssid[33]; int rssi; bool open; };
ScanEntry scanList[48]; uint8_t scanCount=0; bool scanRunning=false,scanDone=false,scanError=false; uint8_t scanTry=0; int scanRaw=0;
void scanStart(uint32_t now) {
  // A pending STA reconnect makes the radio refuse to scan, so park it first; the retry timer resumes it afterwards.
  if(WiFi.status()!=WL_CONNECTED) { WiFi.disconnect(false,false); lastWifi=now; }
  WiFi.scanDelete(); WiFi.scanNetworks(true,true); scanRunning=true;
}
enum class Trial : uint8_t { IDLE, RUNNING, OK, FAIL };
Trial trial=Trial::IDLE; char trialSsid[33]="",trialPassword[65]="",trialReason[20]=""; uint32_t trialStarted=0;
void trialEnd(Trial result,const char* reason,uint32_t now) {
  trial=result; strlcpy(trialReason,reason,sizeof(trialReason)); memset(trialPassword,0,sizeof(trialPassword)); lastWifi=now;
  if(result==Trial::FAIL) { if(network.ssid[0]) WiFi.begin(network.ssid,network.password); else WiFi.disconnect(false,false); } // back to the last good network
}
void wifiTick(uint32_t now) {
  if(scanRunning) {
    int n=WiFi.scanComplete();
    if(n==WIFI_SCAN_FAILED || n==0) {
      scanRaw=0;
      if(++scanTry<3) scanStart(now); // a failed or empty scan is usually transient: try again before giving up
      else { scanRunning=false; scanDone=true; scanCount=0; scanError=n==WIFI_SCAN_FAILED; WiFi.scanDelete(); }
    } else if(n>0) {
      scanCount=0; scanRaw=n;
      for(int i=0;i<n;++i) {
        auto name=WiFi.SSID(i); if(name.length()==0 || name.length()>32) continue; // hidden or malformed
        int rssi=WiFi.RSSI(i); bool open=WiFi.encryptionType(i)==WIFI_AUTH_OPEN,found=false;
        for(uint8_t k=0;k<scanCount;++k) if(!strcmp(scanList[k].ssid,name.c_str())) {
          found=true; if(rssi>scanList[k].rssi) { scanList[k].rssi=rssi; scanList[k].open=open; } break;
        }
        if(found || scanCount>=sizeof(scanList)/sizeof(scanList[0])) continue;
        strlcpy(scanList[scanCount].ssid,name.c_str(),sizeof(scanList[0].ssid)); scanList[scanCount].rssi=rssi; scanList[scanCount].open=open; ++scanCount;
      }
      for(uint8_t a=1;a<scanCount;++a) { ScanEntry v=scanList[a]; int b=a-1; while(b>=0 && scanList[b].rssi<v.rssi) { scanList[b+1]=scanList[b]; --b; } scanList[b+1]=v; }
      if(scanCount>20) scanCount=20;
      WiFi.scanDelete(); scanRunning=false; scanDone=true;
    }
  }
  if(trial==Trial::RUNNING) {
    int st=WiFi.status(); uint32_t elapsed=now-trialStarted;
    if(st==WL_CONNECTED) {
      Network keep=network;
      strlcpy(network.ssid,trialSsid,sizeof(network.ssid)); strlcpy(network.password,trialPassword,sizeof(network.password));
      if(saveNetwork()) { wifiBackoff=30000; trialEnd(Trial::OK,"",now); }
      else { network=keep; trialEnd(Trial::FAIL,"E_WIFI_SAVE",now); }
    } else if(elapsed>3000 && (st==WL_CONNECT_FAILED || st==WL_NO_SSID_AVAIL)) trialEnd(Trial::FAIL,st==WL_NO_SSID_AVAIL?"E_WIFI_NOT_FOUND":"E_WIFI_AUTH",now);
    else if(elapsed>45000) trialEnd(Trial::FAIL,"E_WIFI_TIMEOUT",now); // AP channel switch + slow DHCP can take well over 20 s
  }
}
void wifiGet() {
  if(!webAuth()) return;
  static const char* const names[]={"idle","running","ok","fail"};
  cJSON* root=cJSON_CreateObject(); bool connected=WiFi.status()==WL_CONNECTED;
  cJSON* sta=cJSON_AddObjectToObject(root,"sta"); cJSON_AddBoolToObject(sta,"connected",connected);
  if(connected) {
    cJSON_AddStringToObject(sta,"ip",WiFi.localIP().toString().c_str()); cJSON_AddNumberToObject(sta,"rssi",WiFi.RSSI());
    cJSON_AddStringToObject(sta,"host",HOSTNAME ".local"); cJSON_AddStringToObject(sta,"ssid",WiFi.SSID().c_str());
  }
  cJSON_AddBoolToObject(root,"scanError",scanError); cJSON_AddNumberToObject(root,"scanRaw",scanRaw);
  cJSON_AddStringToObject(root,"saved",network.ssid);
  cJSON* t=cJSON_AddObjectToObject(root,"trial"); cJSON_AddStringToObject(t,"state",names[uint8_t(trial)]);
  cJSON_AddStringToObject(t,"ssid",trialSsid); cJSON_AddStringToObject(t,"reason",trialReason);
  cJSON_AddBoolToObject(root,"scanning",scanRunning); cJSON_AddBoolToObject(root,"scanned",scanDone);
  cJSON* list=cJSON_AddArrayToObject(root,"networks");
  for(uint8_t i=0;i<scanCount;++i) {
    cJSON* n=cJSON_CreateObject(); cJSON_AddStringToObject(n,"ssid",scanList[i].ssid);
    cJSON_AddNumberToObject(n,"rssi",scanList[i].rssi); cJSON_AddBoolToObject(n,"open",scanList[i].open); cJSON_AddItemToArray(list,n);
  }
  char* text=cJSON_PrintUnformatted(root); cJSON_Delete(root);
  web.sendHeader("Cache-Control","no-store"); web.send(200,"application/json",text?text:"{}"); if(text) cJSON_free(text);
}
void wifiPost() {
  if(!webAuth()) return;
  std::string body(web.arg("plain").c_str()); cJSON* in=cJSON_Parse(body.c_str());
  cJSON* op=in?cJSON_GetObjectItemCaseSensitive(in,"op"):nullptr; const char* error=nullptr;
  if(!cJSON_IsString(op)) error="E_JSON";
  else if(trial==Trial::RUNNING) error="E_BUSY";
  else if(!strcmp(op->valuestring,"scan")) {
    scanDone=false; scanError=false; scanTry=0; scanCount=0; scanStart(millis());
  } else if(!strcmp(op->valuestring,"connect")) {
    cJSON* ssid=cJSON_GetObjectItemCaseSensitive(in,"ssid"); cJSON* pass=cJSON_GetObjectItemCaseSensitive(in,"password");
    if(!cJSON_IsString(ssid) || !strlen(ssid->valuestring) || strlen(ssid->valuestring)>32) error="E_WIFI_SSID";
    else if(!cJSON_IsString(pass) || (strlen(pass->valuestring) && (strlen(pass->valuestring)<8 || strlen(pass->valuestring)>64))) error="E_WIFI_PASSWORD";
    else {
      strlcpy(trialSsid,ssid->valuestring,sizeof(trialSsid)); strlcpy(trialPassword,pass->valuestring,sizeof(trialPassword));
      trial=Trial::RUNNING; trialStarted=millis(); trialReason[0]=0;
      WiFi.disconnect(false,false); WiFi.begin(trialSsid,trialPassword);
    }
  } else if(!strcmp(op->valuestring,"forget")) {
    Network keep=network; network.ssid[0]=0; network.password[0]=0;
    if(saveNetwork()) WiFi.disconnect(false,false); else { network=keep; error="E_WIFI_SAVE"; }
  } else error="E_OP";
  cJSON_Delete(in);
  char reply[64]; snprintf(reply,sizeof(reply),"{\"ok\":%s,\"error\":\"%s\"}",error?"false":"true",error?error:"");
  web.sendHeader("Cache-Control","no-store"); web.send(error?409:200,"application/json",reply);
}

void networkTick(uint32_t now) {
  wifiTick(now);
  static bool mdnsOn=false; bool up=WiFi.status()==WL_CONNECTED; // flipclock.local on the home network
  if(up && !mdnsOn) { if(MDNS.begin(HOSTNAME)) { MDNS.addService("http","tcp",80); mdnsOn=true; } }
  else if(!up && mdnsOn) { MDNS.end(); mdnsOn=false; }
  if(network.ssid[0] && WiFi.status()!=WL_CONNECTED && trial!=Trial::RUNNING && uint32_t(now-lastWifi)>=wifiBackoff) {
    lastWifi=now; WiFi.begin(network.ssid,network.password); if(wifiBackoff<300000) wifiBackoff*=2;
  }
  if(WiFi.status()==WL_CONNECTED && !sntpStarted) { // network time is the only time source
    esp_sntp_set_time_sync_notification_cb(sntpCallback); esp_sntp_set_sync_interval(21600000UL);
    configTime(0,0,network.hosts[0],network.hosts[1],network.hosts[2]); sntpStarted=true; wifiBackoff=30000;
  }
  int64_t value;
  if(xQueueReceive(syncQueue,&value,0)==pdTRUE && validUtc(value)) {
    // Every adjustment first pauses; active page is allowed to finish, never interrupted by time update.
    bool wasRunning=!planner.paused;
    pendingSync=value; pendingSyncMs=now; planner.changed(false); largeRequired=false;
    pendingSyncConfirm_=rtc.valid && llabs(value-rtc.utc)>300;
    syncResume=wasRunning && !pendingSyncConfirm_; // only small corrections resume by themselves
    if(pendingSyncConfirm_) strlcpy(lastError,"E_TIME_CONFIRM",sizeof(lastError));
  }
  if(pendingSync && !pendingSyncConfirm_ && !jobSeq && !link.pending && !link.armed() && !systemFault) {
    if(uint32_t(now-pendingSyncMs)>120000) { pendingSync=0; if(syncResume && !systemFault) planner.paused=false; syncResume=false; return; }
    int64_t corrected=pendingSync+uint32_t(now-pendingSyncMs)/1000;
    lastOffset=rtc.valid?corrected-rtc.utc:0;
    if(!rtc.write(corrected,now)) { errorState("E_RTC_WRITE",false); return; }
    lastSync=rtc.utc; pendingSync=0; observedUtc=rtc.utc; observedMs=now; strlcpy(source,"sntp",sizeof(source));
    // A running clock stays running after a small correction; a large one waits for confirm_time and a new preview.
    if(syncResume && !systemFault) planner.paused=false;
    syncResume=false;
  }
}

void localLine(const char* line) {
  if(line[0]=='{') { process(line,false); return; }
  if(!strcmp(line,"status")) { status(0,false); return; }
  if(!strcmp(line,"access")) {
    Serial.printf("WEB wifi=%s password=%s user=admin url=http://192.168.4.1/\n",apName,webPassword);
    if(WiFi.status()==WL_CONNECTED) Serial.printf("LAN url=http://%s/ or http://" HOSTNAME ".local/\n",WiFi.localIP().toString().c_str());
    return;
  }
  if(!strcmp(line,"pause")) { planner.paused=true; saveWasPaused=true; manualPages=0; return; }
  if(!strcmp(line,"stop")) { cancelJob("E_STOPPED"); queuedJog_=0; link.stop(); return; }
  if(!planner.paused || !safeIdle() || link.armed()) { Serial.println("E_BUSY: pause and wait for disarm"); return; }
  if(!strcmp(line,"pair")) {
    passkey=100000+esp_random()%900000; pairUntil=millis()+120000; NimBLEDevice::setSecurityPasskey(passkey.load());
    Serial.printf("PAIR 120s passkey=%06lu\n",(unsigned long)passkey.load()); return;
  }
  if(!strcmp(line,"clear_bonds CONFIRM")) {
    if(peer.load()!=BLE_HS_CONN_HANDLE_NONE) server->disconnect(peer.load());
    Serial.println(NimBLEDevice::deleteAllBonds()?"BONDS_CLEARED":"E_BONDS"); pairUntil=0; return;
  }
  if(!strcmp(line,"reset_config CONFIRM")) {
    if(!store.resetConfig()) { Serial.println("E_NVS"); return; }
    planner.config=Config(); planner.invalidate(); systemFault=false; Serial.println("CONFIG_RESET; RTC preserved; save_config required"); return;
  }
  if(!strncmp(line,"wifi ",5)) {
    cJSON* obj=cJSON_Parse(line+5); cJSON* ssid=cJSON_GetObjectItemCaseSensitive(obj,"ssid"),*password=cJSON_GetObjectItemCaseSensitive(obj,"password");
    bool ok=cJSON_IsString(ssid) && cJSON_IsString(password) && strlen(ssid->valuestring)<=32 && strlen(password->valuestring)<=64;
    if(ok) { strlcpy(network.ssid,ssid->valuestring,sizeof(network.ssid)); strlcpy(network.password,password->valuestring,sizeof(network.password)); ok=saveNetwork(); }
    cJSON_Delete(obj); Serial.println(ok?"WIFI_SAVED":"E_WIFI_CONFIG"); lastWifi=millis()-300000; return;
  }
  if(!strncmp(line,"ntp ",4)) {
    cJSON* obj=cJSON_Parse(line+4); cJSON* a=cJSON_GetObjectItemCaseSensitive(obj,"servers"); Network next=network;
    bool ok=cJSON_IsArray(a) && cJSON_GetArraySize(a)>=1 && cJSON_GetArraySize(a)<=3;
    if(ok) for(int i=0;i<3;++i) {
      cJSON* host=cJSON_GetArrayItem(a,i);
      if(!host) next.hosts[i][0]=0;
      else if(!cJSON_IsString(host) || !strlen(host->valuestring) || strlen(host->valuestring)>63) ok=false;
      else strlcpy(next.hosts[i],host->valuestring,64);
    }
    if(ok) { network=next; ok=saveNetwork(); if(sntpStarted) { esp_sntp_stop(); sntpStarted=false; } }
    cJSON_Delete(obj); Serial.println(ok?"NTP_SAVED":"E_NTP_CONFIG"); return;
  }
  Serial.println("status | access | pause | stop | pair | wifi JSON | ntp JSON | clear_bonds CONFIRM | reset_config CONFIRM | JSONL");
}

// Pending operations belong to the loop, never to callbacks.
void supervisor(uint32_t now) {
  if(link.fault) {
    if(!systemFault) { cancelJob("E_I2C"); errorState("E_I2C"); }
    if(savePending) { if(saveRequest) reject(saveRequest,"E_I2C",saveBle); savePending=false; }
    return;
  }
  if(lastLinkReady && !link.ready && !clearRequest_) { cancelJob("E_UNO_RESET"); errorState("E_UNO_RESET"); }
  lastLinkReady=link.ready;
  if(link.ready && link.status.op()==FAULT && !clearRequest_) {
    if(!systemFault) { cancelJob("E_UNO_FAULT"); errorState("E_UNO_FAULT"); }
    return;
  }
  // Automatic restore after power loss: resume once, then catch up to the current RTC time.
  if(restoreActive) {
    if(systemFault || !planner.position) restoreActive=false;
    else if(rtc.valid && link.ready && safeIdle() && planner.paused && !pendingSync && !link.armed()) {
      restoreActive=false; planner.paused=false; largeConfirmed_=true;
    }
  }
  if(stopRequest_ && !link.pending && link.coilZero() && !link.armed()) {
    respond(stopRequest_,"completed",",\"coil_outputs_zero\":true",stopBle_); stopRequest_=0;
  }
  if(clearRequest_ && link.ready && !link.pending) {
    if(link.armed() || link.running()) { link.stop(); return; }
    if(link.status.op()==FAULT || clearSent_==0) { if(link.send(CLEAR)) clearSent_=link.seq; return; }
    if(link.acknowledged==clearSent_) {
      if(link.result==flip::OK) { systemFault=false; lastError[0]=0; respond(clearRequest_,"completed",nullptr,clearBle_); }
      else { errorState("E_CLEAR"); reject(clearRequest_,"E_I2C",clearBle_); }
      clearRequest_=clearSent_=0;
    }
    return;
  }
  if(jobSeq && !link.pending && link.acknowledged==jobSeq && link.result!=flip::OK) {
    cancelJob("E_MOVE_REJECTED"); errorState("E_MOVE_REJECTED"); return;
  }
  if(jobSeq && link.status.session()==link.session && link.status.seq()==jobSeq && link.status.op()==DONE) {
    if(link.status.steps()!=jobSteps || link.status.arg(1)!=0 || !link.coilZero() || uint8_t(get16(link.status.bytes+28))!=flip::OK) {
      cancelJob("E_BAD_DONE"); errorState("E_BAD_DONE"); return;
    }
    if(!jobJog && !planner.commit(jobSeq,nextR,jobPages)) { cancelJob("E_COMMIT"); errorState("E_COMMIT"); return; }
    if(jobJog) {
      char extra[120]; snprintf(extra,sizeof(extra),",\"job_id\":%lu,\"steps_sent\":%ld,\"position_confidence\":\"unknown\"",(unsigned long)jobSeq,(long)jobSteps);
      respond(jobRequest,"completed",extra,jobBle);
    }
    if(manualRequest) manualCompleted_=uint16_t(manualCompleted_+jobPages);
    if(manualPages) manualPages=manualPages>jobPages?uint16_t(manualPages-jobPages):0;
    jobSeq=jobRequest=0; jobPages=1; lastSettle=now;
    if(manualRequest && (!manualPages || planner.manualPause)) {
      char extra[120]; snprintf(extra,sizeof(extra),",\"pages_completed\":%u,\"requested_pages\":%u,\"paused\":%s",
        manualCompleted_,manualRequested_,manualCompleted_<manualRequested_?"true":"false");
      respond(manualRequest,"completed",extra,manualBle); manualRequest=0;
    }
  }
  if(jobSeq || link.pending) return;
  if(queuedJog_ && !systemFault) {
    if(!link.armed()) { if(link.ready && link.send(ARM,planner.config.rate,120000)) armSeq=link.seq; return; }
    if(armSeq && link.acknowledged==armSeq && link.result!=flip::OK) { reject(queuedJogRequest_,"E_I2C",queuedJogBle_); queuedJog_=0; errorState("E_ARM"); return; }
    if(startJob(true,queuedJog_,queuedJogRequest_,queuedJogBle_)) queuedJog_=0;
    return;
  }
  bool wantsMove=((!planner.paused && rtc.valid) || manualPages) && planner.position && planner.config.mechanics && !systemFault;
  if(!wantsMove || savePending || pendingSync) {
    if(link.armed()) { link.send(DISARM); return; }
    if(pauseRequest_) { respond(pauseRequest_,"completed",",\"paused\":true",pauseBle_); pauseRequest_=0; }
    if(savePending && link.ready && link.coilZero()) {
      bool ok=store.save(planner,rtc,uint8_t(get16(link.status.bytes+28)>>8),now);
      if(saveRequest) {
        if(ok) respond(saveRequest,"completed",",\"persisted\":true",saveBle); else reject(saveRequest,store.throttled?"E_SAVE_THROTTLED":"E_NVS",saveBle);
      }
      if(!ok && !store.throttled) errorState("E_NVS",false);
      if(ok && planner.position) { savedDisplay=planner.display; savedRemainder=planner.remainder; }
      // Resume only if nothing (pause, stop, config, time or position change) happened while the save was in flight.
      planner.paused=saveWasPaused || planner.revision!=saveRevision; savePending=false; saveRequest=0; lastCheckpoint=now;
    }
    return;
  }
  if(uint32_t(now-lastSettle)<planner.config.settle || !link.ready) return;
  if(planner.config.checkpoint && uint32_t(now-lastCheckpoint)>=uint32_t(planner.config.checkpoint)*60000UL) {
    savePending=true; saveRequest=0; saveWasPaused=planner.paused; saveRevision=planner.revision; planner.paused=true; return;
  }
  uint16_t pages=manualPages?manualPages:pagesBehind(rtc.utc,planner.config,planner.display);
  if(!pages) {
    largeConfirmed_=false;
    if(link.armed()) { link.send(DISARM); return; }
    // Caught up: persist the position so a power loss restores to this page, not an older one.
    if(planner.position && rtc.valid && planner.config.mechanics && !jobSeq &&
       (int32_t(planner.display)!=savedDisplay || planner.remainder!=savedRemainder)) {
      savePending=true; saveRequest=0; saveWasPaused=planner.paused; saveRevision=planner.revision; planner.paused=true;
    }
    return;
  }
  uint32_t steps=0;
  if(!pageSteps(planner.config.q,planner.remainder,1,steps,nextR)) { errorState("E_PLAN"); return; }
  uint64_t estimate=uint64_t(estimateMs(steps,planner.config))*pages;
  // Several pages are driven as ONE move so the motor can reach cruise speed between the start ramp and the
  // arrival ramp. Bounded by the Uno's per-move step limit and by the 120 s move timeout.
  uint16_t chunk=1; uint32_t chunkSteps=steps,chunkNext=nextR;
  if(pages>1) {
    uint64_t byLimit=(uint64_t(CHUNK_STEPS)*D)/planner.config.q; if(byLimit<1) byLimit=1;
    chunk=uint16_t(pages<byLimit?pages:byLimit);
    while(chunk>1 && (!pageSteps(planner.config.q,planner.remainder,chunk,chunkSteps,chunkNext) ||
          chunkSteps>CHUNK_STEPS || moveTimeoutMs(chunkSteps)>120000UL)) chunk=uint16_t(chunk/2);
    if(!pageSteps(planner.config.q,planner.remainder,chunk,chunkSteps,chunkNext)) { errorState("E_PLAN"); return; }
  }
  if(!manualPages && !largeConfirmed_ && (pages>planner.config.maxPages || estimate>uint32_t(planner.config.maxSeconds)*1000)) {
    planner.paused=true; largeRequired=true; return;
  }
  if(moveTimeoutMs(steps)>120000UL) {
    planner.paused=true; strlcpy(lastError,"E_PAGE_TIMEOUT_RANGE",sizeof(lastError));
    if(manualRequest) { reject(manualRequest,"E_RANGE",manualBle); manualRequest=0; manualPages=0; }
    return;
  }
  if(!link.armed()) {
    if(armSeq && link.acknowledged==armSeq && link.result!=flip::OK) { errorState("E_ARM"); return; }
    if(link.send(ARM,planner.config.rate,120000)) armSeq=link.seq;
    return;
  }
  nextR=chunkNext;
  if(!startJob(false,int32_t(chunkSteps)*planner.config.direction,0,false)) errorState("E_START");
  else jobPages=chunk;
}
void setupApp() {
  Serial.begin(115200); snprintf(bootId,sizeof(bootId),"%08lx",(unsigned long)esp_random());
  rxQueue=xQueueCreate(4,sizeof(Chunk)); txQueue=xQueueCreate(4,sizeof(Reply)); syncQueue=xQueueCreate(1,sizeof(int64_t));
  if(!rxQueue || !txQueue || !syncQueue) { Serial.println("FATAL queues"); while(true) delay(1000); }
  Wire.begin(13,14,100000); Wire.setTimeOut(20);
  if(!store.begin(planner.config)) errorState("E_NVS",false);
  link.begin(); loadNetwork(); restoreSnapshot();
  snprintf(apName,sizeof(apName),"FlipClock-%04x",unsigned(ESP.getEfuseMac()&0xffff));
  WiFi.persistent(false); WiFi.setHostname(HOSTNAME); WiFi.mode(WIFI_AP_STA); lastWifi=millis()-300000; webSetup();
  char name[24]; strlcpy(name,apName,sizeof(name));
  NimBLEDevice::init(name); NimBLEDevice::setSecurityAuth(true,true,true);
  NimBLEDevice::setSecurityIOCap(BLE_HS_IO_DISPLAY_ONLY);
  passkey=100000+esp_random()%900000; NimBLEDevice::setSecurityPasskey(passkey.load());
  server=NimBLEDevice::createServer(); server->setCallbacks(&serverCallbacks);
  NimBLEService* service=server->createService(SERVICE);
  auto* rx=service->createCharacteristic(RX,NIMBLE_PROPERTY::WRITE|NIMBLE_PROPERTY::WRITE_ENC|NIMBLE_PROPERTY::WRITE_AUTHEN,512);
  rx->setCallbacks(&rxCallbacks);
  eventTx=service->createCharacteristic(TX,NIMBLE_PROPERTY::INDICATE|NIMBLE_PROPERTY::READ_ENC|NIMBLE_PROPERTY::READ_AUTHEN,512);
  eventTx->setCallbacks(&txCallbacks);
  auto* info=service->createCharacteristic(INFO,NIMBLE_PROPERTY::READ,20);
  char shortInfo[21]; snprintf(shortInfo,sizeof(shortInfo),"1|0.3.0|%s",bootId); info->setValue(shortInfo);
  server->start(); auto* adv=NimBLEDevice::getAdvertising(); adv->addServiceUUID(SERVICE); adv->setName(name); adv->enableScanResponse(true); adv->start();
  Serial.printf("FlipClock 0.3.0 protocol=1 board=AI_THINKER_ESP32_CAM_DUAL_UNO boot_id=%s reset=%d %s\n",bootId,int(esp_reset_reason()),
    restoreActive?"RESTORE_PENDING":"BOOT_SAFE");
  Serial.println("No camera/SD/OTA. UART: status / access / pair / wifi JSON / JSONL. Web: http://192.168.4.1/");
  lastCheckpoint=millis();
}
void loopApp() {
  uint32_t now=millis(); link.tick(now);
  if(disconnected.exchange(false)) {
    bleLines.reset(); xQueueReset(rxQueue); xQueueReset(txQueue); queuedJog_=0;
    if(manualPages || jobJog) { planner.paused=true; manualPages=0; }
    NimBLEDevice::getAdvertising()->start();
  }
  if(rxOverflow_.exchange(false)) {
    bleLines.reset(); planner.paused=true; strlcpy(lastError,"E_RX_OVERFLOW",sizeof(lastError)); server->disconnect(peer.load());
  }
  if(!pairOpen() && peer.load()!=BLE_HS_CONN_HANDLE_NONE && !authenticated.load()) server->disconnect(peer.load());
  // Bound transport work per loop so I2C heartbeat and STOP retain time to run.
  Chunk packet;
  if(xQueueReceive(rxQueue,&packet,0)==pdTRUE && packet.epoch==connectionEpoch.load() && authenticated.load()) {
    for(uint16_t i=0;i<packet.length;++i) {
      auto result=bleLines.push(packet.bytes[i],now);
      if(result==Lines::LINE) process(bleLines.data,true);
      else if(result==Lines::TOO_LONG) reject(0,"E_FRAME_TOO_LONG",true);
    }
  }
  for(uint8_t n=0;n<64 && Serial.available();++n) {
    uint8_t b=uint8_t(Serial.read()); if(b=='\r') continue;
    auto result=uartLines.push(b,now);
    if(result==Lines::LINE) localLine(uartLines.data);
    else if(result==Lines::TOO_LONG) Serial.println("E_FRAME_TOO_LONG");
  }
  if(bleLines.tick(now)==Lines::TIMEOUT) reject(0,"E_FRAME_TIMEOUT",true);
  if(uartLines.tick(now)==Lines::TIMEOUT) Serial.println("E_FRAME_TIMEOUT");
  if(uint32_t(now-lastRtc)>=250) {
    lastRtc=now;
    if(rtc.read(now)) {
      if(observedUtc && (rtc.utc<observedUtc || llabs((rtc.utc-observedUtc)-int64_t(uint32_t(now-observedMs)/1000))>3)) {
        planner.changed(false); manualPages=0; strlcpy(lastError,"E_TIME_JUMP",sizeof(lastError));
      }
      observedUtc=rtc.utc; observedMs=now;
    }
    if(!rtc.valid && !planner.paused) { planner.paused=true; manualPages=0; strlcpy(lastError,"E_TIME_INVALID",sizeof(lastError)); }
  }
  web.handleClient(); networkTick(now); supervisor(now); txTick(now); delay(1);
}
} // namespace clockapp
void clockSetup() { clockapp::setupApp(); }
void clockLoop() { clockapp::loopApp(); }
