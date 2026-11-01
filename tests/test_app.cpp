// Production app.cpp + production services against deterministic I2C/NVS/BLE adapters.
#include "../firmware/esp32_clock/app.cpp"
#include <assert.h>
using namespace clockapp;
static unsigned checks=0;
#define CHECK(x) do { ++checks; if(!(x)) { fprintf(stderr,"FAIL app line %d: %s output=%s\n",__LINE__,#x,Serial.output.c_str()); return 1; } } while(0)
static uint32_t requestId=0;
std::string request(const char* op,const char* args="") {
  char b[513]; snprintf(b,sizeof(b),"{\"v\":1,\"id\":%u,\"boot_id\":\"%s\",\"op\":\"%s\"%s}",++requestId,bootId,op,args); return b;
}
void commandLine(const char* op,const char* args="") { Serial.output.clear(); std::string s=request(op,args); process(s.c_str(),false); }
void spin(uint32_t ms) { uint32_t start=fakeMs; while(uint32_t(fakeMs-start)<ms) loopApp(); }
bool contains(const char* s) { return Serial.output.find(s)!=std::string::npos; }
int main() {
  setupApp(); spin(1000);
  CHECK(link.ready && !fakeUno.armed && fakeUno.mask==0 && !planner.position && planner.paused);
  CHECK(rtc.valid && !systemFault);
  commandLine("resume",",\"plan_id\":1"); CHECK(contains("E_PLAN_STALE")); CHECK(fakeUno.job==0);
  commandLine("jog_steps",",\"steps\":-1"); CHECK(contains("E_REVERSE_DISABLED"));
  commandLine("set_config",",\"values\":{\"mechanics_confirmed\":true,\"steps_per_page_u6\":136533333,\"cycle_minutes\":720}");
  CHECK(contains("completed") && planner.config.mechanics && store.dirty);
  commandLine("set_config",",\"values\":{\"max_step_rate\":1001}"); CHECK(contains("E_RANGE") && planner.config.rate==200);
  commandLine("set_config",",\"values\":{\"acceleration\":4001}"); CHECK(contains("E_RANGE") && planner.config.accel==100);
  commandLine("set_display",",\"hour\":8,\"minute\":0,\"aligned\":true"); CHECK(planner.position && planner.display==480);
  std::string jog=request("jog_steps",",\"steps\":4"); Serial.output.clear(); process(jog.c_str(),false); spin(2500);
  CHECK(contains("steps_sent\":4") && !planner.position && fakeUno.executed==4 && !fakeUno.mask);
  uint32_t accepts=Wire.moveAccepts;
  Serial.output.clear(); process(jog.c_str(),false); spin(200); CHECK(Wire.moveAccepts==accepts && contains("completed"));
  std::string reuse=jog; reuse[reuse.find("steps\":4")+7]='5'; process(reuse.c_str(),false); CHECK(contains("E_ID_REUSE") && Wire.moveAccepts==accepts);
  commandLine("set_display",",\"hour\":8,\"minute\":0,\"aligned\":true");
  commandLine("advance_pages",",\"pages\":2"); spin(7000);
  CHECK(planner.display==482 && planner.remainder==66666 && !jobSeq && !fakeUno.armed);
  CHECK(contains("pages_completed\":2"));
  commandLine("save_config"); spin(500);
  CHECK(contains("persisted\":true") && store.saved.generation==1 && store.saved.hasSnapshot);
  commandLine("save_config"); spin(100); CHECK(contains("persisted\":true") && store.writes==1 && !systemFault);
  commandLine("set_config",",\"values\":{\"settle_ms\":250}"); commandLine("save_config"); spin(100);
  CHECK(contains("E_SAVE_THROTTLED") && store.saved.generation==1 && !systemFault && store.dirty);
  commandLine("set_config",",\"values\":{\"settle_ms\":200}");
  Store rebootStore; Config loaded; CHECK(rebootStore.begin(loaded) && loaded.q==136533333ULL);
  Planner rebootPlanner; rebootPlanner.config=loaded; CHECK(!rebootPlanner.position && rebootPlanner.paused);
  commandLine("preview_sync"); uint32_t plan=planner.preview.id; CHECK(plan && contains("plan_id"));
  commandLine("set_config",",\"values\":{\"utc_offset_min\":420}");
  char args[100]; snprintf(args,sizeof(args),",\"plan_id\":%u,\"confirm_large\":true",plan);
  commandLine("resume",args); CHECK(contains("E_PLAN_STALE"));
  commandLine("set_time",",\"utc_s\":1793462400"); CHECK(contains("completed") && !planner.config.autoTime && !strcmp(source,"ble_manual"));
  int64_t proposed=1793466000LL; xQueueOverwrite(syncQueue,&proposed); spin(500); CHECK(!pendingSync && !strcmp(source,"ble_manual"));
  commandLine("set_config",",\"values\":{\"auto_time\":true}"); xQueueOverwrite(syncQueue,&proposed); spin(500);
  CHECK(pendingSync==proposed && pendingSyncConfirm_ && planner.paused);
  commandLine("confirm_time",",\"utc_s\":1793466000"); CHECK(!pendingSync && !strcmp(source,"sntp"));
  commandLine("advance_pages",",\"pages\":5"); spin(200);
  commandLine("pause"); spin(9000); CHECK(!jobSeq && !manualPages && planner.position && !fakeUno.armed); // pause lets the whole continuous move finish
  commandLine("advance_pages",",\"pages\":1"); spin(350); CHECK(jobSeq);
  commandLine("stop"); spin(500); CHECK(!planner.position && !fakeUno.armed && !fakeUno.mask && contains("coil_outputs_zero\":true"));
  commandLine("set_display",",\"hour\":9,\"minute\":0,\"aligned\":true");
  commandLine("advance_pages",",\"pages\":1"); spin(300); fakeUno=Endpoint(); spin(300);
  CHECK(systemFault && !planner.position && !fakeUno.armed && !fakeUno.mask);
  commandLine("clear_fault"); spin(2000); CHECK(!systemFault && link.ready && !planner.position);
  commandLine("set_display",",\"hour\":9,\"minute\":0,\"aligned\":true");
  commandLine("advance_pages",",\"pages\":1"); spin(300); Wire.unoMissing=true; spin(2500);
  CHECK(systemFault && !fakeUno.armed && !fakeUno.mask && !planner.position);
  Wire.unoMissing=false; commandLine("clear_fault"); spin(2500); CHECK(!systemFault && link.ready);
  // ---- Web console: authenticated, same protocol, client-supplied ids ignored ----
  auto webCmd=[](const char* body) { web.body=body; web.post["/api/cmd"](); return web.lastBody; };
  auto has=[](const std::string& s,const char* needle) { return s.find(needle)!=std::string::npos; };
  CHECK(WiFi.apName.rfind("FlipClock-",0)==0 && strlen(webPassword)==12 && WiFi.apPassword==webPassword && web.begun);
  CHECK(fakeNvs["flip-web"]["pw"].size()==13);
  web.get["/"](); CHECK(web.lastCode==200 && has(web.lastBody,"翻頁時鐘") && has(web.lastType,"text/html"));
  web.authOk=false; web.get["/api/state"](); CHECK(web.lastCode==401 && web.lastBody.empty());
  uint32_t accepted=Wire.moveAccepts; web.body="{\"op\":\"jog_steps\",\"steps\":4}"; web.post["/api/cmd"]();
  CHECK(web.lastCode==401 && Wire.moveAccepts==accepted && !queuedJog_); web.authOk=true;
  web.get["/api/state"](); { cJSON* j=cJSON_Parse(web.lastBody.c_str()); CHECK(j && cJSON_IsString(cJSON_GetObjectItemCaseSensitive(j,"state"))); cJSON_Delete(j); }
  CHECK(has(webCmd("not json"),"E_JSON") && has(webCmd("{\"op\":1}"),"E_JSON"));
  CHECK(has(webCmd("{\"op\":\"bogus\"}"),"E_OP"));
  CHECK(has(webCmd("{\"v\":9,\"id\":1,\"boot_id\":\"zz\",\"op\":\"get_config\"}"),"\"phase\":\"completed\""));
  std::string reply=webCmd("{\"op\":\"set_display\",\"hour\":8,\"minute\":0,\"aligned\":true}");
  CHECK(has(reply,"completed") && planner.position && planner.display==480);
  reply=webCmd("{\"op\":\"advance_pages\",\"pages\":3}"); CHECK(has(reply,"accepted"));
  web.get["/api/state"](); CHECK(has(web.lastBody,"\"busy\":true"));
  CHECK(has(webCmd("{\"op\":\"set_time\",\"utc_s\":1793462400}"),"E_BUSY"));
  spin(12000); web.get["/api/state"](); CHECK(has(web.lastBody,"\"busy\":false") && has(web.lastBody,"\"display\":483") && planner.display==483);
  CHECK(has(webCmd("{\"op\":\"save_config\"}"),"accepted")); spin(500);
  CHECK(store.saved.hasSnapshot && store.saved.display==483 && !store.dirty);
  // ---- Power cycle: NVS and RTC survive, volatile state is lost, position is restored and caught up ----
  int64_t base=1793462400LL+86400; uint16_t now0=target(base,planner.config);
  int64_t wanted=base+int64_t((uint16_t((483+3)%720)+720-now0)%720)*60;
  char timeBody[80]; snprintf(timeBody,sizeof(timeBody),"{\"op\":\"set_time\",\"utc_s\":%lld}",(long long)wanted);
  CHECK(has(webCmd(timeBody),"completed") && target(rtc.utc,planner.config)==486);
  Config persisted; planner=Planner(); store=Store(); CHECK(store.begin(persisted)); planner.config=persisted;
  restoreActive=false; restoredFromSnapshot=false; savedDisplay=-1; largeConfirmed_=false;
  CHECK(restoreSnapshot() && planner.position && planner.display==483 && planner.paused && restoreActive && planner.config.mechanics);
  web.get["/api/state"](); CHECK(has(web.lastBody,"\"restoring\":true") && has(web.lastBody,"\"pos\":true"));
  planner.config.maxPages=1; // 3 pages exceeds the interactive limit; a restore must still catch up without a prompt
  spin(500); CHECK(!restoreActive && !planner.paused && largeConfirmed_ && restoredFromSnapshot);
  spin(14000); CHECK(planner.display==486 && !fakeUno.armed && !fakeUno.mask && !largeConfirmed_ && !systemFault);
  CHECK(savedDisplay==486 && store.saved.display==486 && !planner.paused && !largeRequired);
  // Any deliberate action cancels a pending restore, and an unconfirmed-mechanics snapshot is never restored.
  commandLine("pause"); spin(500); restoreActive=false;
  planner=Planner(); planner.config=persisted; Saved untrusted=store.saved; untrusted.config.mechanics=false;
  Saved keep=store.saved; store.saved=untrusted; CHECK(!restoreSnapshot() && !planner.position); store.saved=keep;
  planner.config=persisted; CHECK(restoreSnapshot() && restoreActive); commandLine("pause"); CHECK(!restoreActive);
  // ---- Wi-Fi provisioning: scan, verified connect, save only after a real connection ----
  {
    auto postWifi=[&](const char* body) { web.body=body; web.post["/api/wifi"](); return web.lastBody; };
    auto getWifi=[&]() { web.get["/api/wifi"](); return web.lastBody; };
    std::string json=getWifi(); CHECK(has(json,"\"scanning\":false") && has(json,"\"networks\":[]") && has(json,"\"state\":\"idle\""));
    web.authOk=false; postWifi("{\"op\":\"scan\"}"); CHECK(web.lastCode==401 && WiFi.scanCalls==0); web.authOk=true;
    WiFi.nets={{"Home",-40,WIFI_AUTH_WPA2_PSK},{"Cafe \"Free\"",-70,WIFI_AUTH_OPEN},{"Home",-80,WIFI_AUTH_WPA2_PSK},{"",-30,WIFI_AUTH_OPEN},{"Far",-90,WIFI_AUTH_WPA2_PSK}};
    CHECK(has(postWifi("{\"op\":\"scan\"}"),"\"ok\":true") && WiFi.scanCalls==1); CHECK(has(getWifi(),"\"scanning\":true"));
    spin(50); json=getWifi(); CHECK(has(json,"\"scanning\":false") && has(json,"\"scanned\":true"));
    { cJSON* j=cJSON_Parse(json.c_str()); cJSON* list=cJSON_GetObjectItemCaseSensitive(j,"networks");
      CHECK(cJSON_GetArraySize(list)==3 && !strcmp(cJSON_GetArrayItem(list,0)->child->valuestring,"Home") &&
            !strcmp(cJSON_GetObjectItemCaseSensitive(cJSON_GetArrayItem(list,1),"ssid")->valuestring,"Cafe \"Free\"") &&
            cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(cJSON_GetArrayItem(list,1),"open")) &&
            cJSON_GetObjectItemCaseSensitive(cJSON_GetArrayItem(list,0),"rssi")->valueint==-40); cJSON_Delete(j); }
    { int before=WiFi.scanCalls; WiFi.failScans=2; postWifi("{\"op\":\"scan\"}"); spin(80); json=getWifi();
      CHECK(WiFi.scanCalls==before+3 && has(json,"\"scanned\":true") && has(json,"\"scanError\":false") && has(json,"\"Home\"")); // transient failures are retried
      WiFi.failScans=9; postWifi("{\"op\":\"scan\"}"); spin(80); json=getWifi();
      CHECK(has(json,"\"scanError\":true") && has(json,"\"networks\":[]") && has(json,"\"scanning\":false")); WiFi.failScans=0; // gives up with a visible error
      postWifi("{\"op\":\"scan\"}"); spin(50); }
    CHECK(has(postWifi("{\"op\":\"connect\",\"ssid\":\"Home\",\"password\":\"short\"}"),"E_WIFI_PASSWORD") && web.lastCode==409);
    CHECK(has(postWifi("{\"op\":\"connect\",\"ssid\":\"\",\"password\":\"\"}"),"E_WIFI_SSID") && !WiFi.beganSsid.size());
    CHECK(has(postWifi("{\"op\":\"bogus\"}"),"E_OP") && has(postWifi("nonsense"),"E_JSON"));
    // Wrong password: nothing is saved and the previous (here: no) network is restored.
    size_t nvsBefore=fakeNvs["flip-network"]["config"].size();
    CHECK(has(postWifi("{\"op\":\"connect\",\"ssid\":\"Home\",\"password\":\"wrong-password\"}"),"\"ok\":true") && WiFi.beganSsid=="Home");
    CHECK(has(postWifi("{\"op\":\"connect\",\"ssid\":\"Home\",\"password\":\"another-one\"}"),"E_BUSY") && has(getWifi(),"\"state\":\"running\""));
    WiFi.state=WL_CONNECT_FAILED; spin(2000); CHECK(has(getWifi(),"\"state\":\"running\"")); spin(2000);
    json=getWifi(); CHECK(has(json,"\"state\":\"fail\"") && has(json,"E_WIFI_AUTH") && !network.ssid[0] && !trialPassword[0] &&
      fakeNvs["flip-network"]["config"].size()==nvsBefore && WiFi.disconnected);
    CHECK(!has(json,"wrong-password")); // the password never leaves the device
    // Timeout.
    WiFi.state=WL_DISCONNECTED; postWifi("{\"op\":\"connect\",\"ssid\":\"Home\",\"password\":\"right-password\"}"); WiFi.state=WL_DISCONNECTED;
    spin(46000); json=getWifi(); CHECK(has(json,"E_WIFI_TIMEOUT") && !network.ssid[0]);
    // Verified connection: saved, persisted across a reload, password cleared from RAM trial buffer.
    postWifi("{\"op\":\"connect\",\"ssid\":\"Home\",\"password\":\"right-password\"}"); WiFi.state=WL_CONNECTED; spin(200);
    json=getWifi(); CHECK(has(json,"\"state\":\"ok\"") && has(json,"192.168.1.77") && has(json,"\"connected\":true") && has(json,"\"saved\":\"Home\"") && !trialPassword[0]);
    { Network live=network; network=Network(); loadNetwork(); CHECK(!strcmp(network.ssid,"Home") && !strcmp(network.password,"right-password")); network=live; }
    // A failed attempt on another network goes back to the saved one.
    postWifi("{\"op\":\"connect\",\"ssid\":\"Other\",\"password\":\"other-password\"}"); WiFi.state=WL_NO_SSID_AVAIL; spin(3500);
    json=getWifi(); CHECK(has(json,"E_WIFI_NOT_FOUND") && !strcmp(network.ssid,"Home") && WiFi.beganSsid=="Home" && !strcmp(network.password,"right-password"));
    // Connected but the save fails: reported as failure, old credentials kept.
    WiFi.state=WL_DISCONNECTED; postWifi("{\"op\":\"connect\",\"ssid\":\"New\",\"password\":\"new-password1\"}"); WiFi.state=WL_CONNECTED;
    nvsWriteFailure=true; spin(200); nvsWriteFailure=false; json=getWifi(); CHECK(has(json,"E_WIFI_SAVE") && !strcmp(network.ssid,"Home"));
    // Forget.
    CHECK(has(postWifi("{\"op\":\"forget\"}"),"\"ok\":true") && !network.ssid[0] && WiFi.disconnected);
    { Network live=network; network.ssid[0]='x'; loadNetwork(); CHECK(!network.ssid[0]); network=live; }
    WiFi.state=WL_DISCONNECTED;
  }
  // ---- NTP correction: small ones keep a running clock running; large ones wait for confirmation ----
  {
    planner.config.autoTime=true; planner.display=target(rtc.utc,planner.config); planner.position=true; planner.paused=false; largeConfirmed_=false;
    spin(2500); CHECK(!planner.paused && !jobSeq);
    int64_t small=rtc.utc+20; xQueueOverwrite(syncQueue,&small); spin(1500);
    CHECK(!pendingSync && !strcmp(source,"sntp") && !planner.paused);
    int64_t large=rtc.utc+4000; xQueueOverwrite(syncQueue,&large); spin(500);
    CHECK(pendingSync==large && pendingSyncConfirm_ && planner.paused && !syncResume);
    web.get["/api/state"](); CHECK(has(web.lastBody,"\"syncAsk\":true") && has(web.lastBody,"\"ntp\":true"));
    pendingSync=0; pendingSyncConfirm_=false; planner.paused=true; spin(300); planner.config.autoTime=false;
    CHECK(planner.paused); // a background save that finishes after this must not undo the pause
  }
  // ---- A pause or change that arrives while a background position save is in flight must win ----
  {
    planner.paused=true; spin(4000); CHECK(!fakeUno.armed && !jobSeq); // let any earlier catch-up finish and disarm
    planner.paused=false; planner.position=true; planner.display=target(rtc.utc,planner.config); lastCheckpoint=fakeMs-uint32_t(planner.config.checkpoint)*60000UL-1;
    spin(1); CHECK(savePending && planner.paused); // checkpoint save has started, not yet finished
    commandLine("pause"); spin(1500); CHECK(!savePending && planner.paused); // pause during the save is kept
    planner.paused=false; lastCheckpoint=fakeMs-uint32_t(planner.config.checkpoint)*60000UL-1; savedDisplay=-1;
    spin(1); CHECK(savePending); planner.changed(false); spin(1500); CHECK(!savePending && planner.paused); // so is any other planner change
    planner.paused=false; savedDisplay=int32_t(planner.display); lastCheckpoint=fakeMs-uint32_t(planner.config.checkpoint)*60000UL-1;
    spin(1500); CHECK(!savePending && !planner.paused); // an undisturbed save still resumes the running clock
    planner.paused=true;
  }
  // ---- PCF8563 module (HW-689): found at 0x51, same time semantics as the DS3231 path ----
  {
    int64_t savedBase=Wire.rtcBase; uint32_t savedAt=Wire.rtcAt; Wire.pcf=true; Rtc chip;
    CHECK(chip.read(fakeMs) && chip.valid && chip.pcf8563() && chip.utc>=savedBase);
    for(int64_t want:{calendarUtc(2028,2,29,23,59,30),calendarUtc(2031,12,31,23,59,58),1800000000LL}) {
      CHECK(chip.write(want,fakeMs) && chip.valid && chip.utc>=want && chip.utc<=want+2);
    }
    Wire.rtcMissing=true; CHECK(!chip.read(fakeMs) && chip.errors>0); Wire.rtcMissing=false;
    CHECK(chip.read(fakeMs) && chip.valid); // re-detected after the device returns
    Wire.pcf=false; Wire.rtcBase=savedBase; Wire.rtcAt=savedAt; Rtc ds; CHECK(ds.read(fakeMs) && !ds.pcf8563());
  }
  // ---- Fast zeroing: many pages are ONE continuous move (ramp up, cruise, ramp down), not one move per page ----
  // The simulated Uno advances once per millisecond, so 500 steps/s is the fastest rate it reproduces exactly.
  commandLine("set_config",",\"values\":{\"max_step_rate\":500,\"acceleration\":3000}");
  CHECK(contains("completed") && planner.config.rate==500 && planner.config.accel==3000);
  {
    uint16_t d0=planner.display; uint32_t moves=Wire.moveAccepts,t0=fakeMs; CHECK(planner.position);
    commandLine("advance_pages",",\"pages\":100"); CHECK(contains("accepted"));
    spin(34000);
    CHECK(!jobSeq && !manualPages && planner.display==uint16_t((d0+100)%720) && !fakeUno.armed && manualCompleted_==100);
    CHECK(Wire.moveAccepts-moves==2 && fakeMs-t0<40000); // 65 + 35 pages; the per-page profile needed ~4 minutes
    commandLine("advance_pages",",\"pages\":721"); CHECK(contains("E_RANGE"));
    commandLine("jog_steps",",\"steps\":2000"); spin(8000); CHECK(!jobSeq && !queuedJog_ && fakeUno.executed==2000 && !fakeUno.mask);
    commandLine("jog_steps",",\"steps\":8001"); CHECK(contains("E_RANGE"));
  }
  // ---- OTA over HTTP: idle-only, validated, never half-applied ----
  auto upload=[](HTTPUploadStatus status,std::string& bytes) {
    web.current.status=status; web.current.buf=reinterpret_cast<uint8_t*>(&bytes[0]); web.current.currentSize=bytes.size(); web.uploader["/api/ota"]();
  };
  std::string image(70000,'x'); image[0]=char(0xE9); std::string none;
  auto sendImage=[&](std::string& bytes) {
    upload(UPLOAD_FILE_START,none); upload(UPLOAD_FILE_WRITE,bytes); upload(UPLOAD_FILE_END,none); web.post["/api/ota"]();
  };
  ESP.restarted=false; Update=FakeUpdate();
  web.authOk=false; sendImage(image); CHECK(web.lastCode==401 && !Update.began && Update.data.empty() && !ESP.restarted); web.authOk=true;
  queuedJog_=4; sendImage(image); CHECK(web.lastCode==409 && has(web.lastBody,"E_BUSY") && !Update.began && !ESP.restarted); queuedJog_=0;
  link.retry(); spin(1500); CHECK(link.ready && !systemFault);
  std::string bad(70000,'x'); sendImage(bad); CHECK(web.lastCode==409 && has(web.lastBody,"E_OTA_IMAGE") && Update.aborted && Update.data.empty() && !ESP.restarted);
  Update=FakeUpdate(); Update.failBegin=true; sendImage(image); CHECK(web.lastCode==409 && has(web.lastBody,"E_OTA_NO_PARTITION") && !ESP.restarted);
  Update=FakeUpdate(); std::string tiny(100,'x'); tiny[0]=char(0xE9); sendImage(tiny); CHECK(web.lastCode==409 && has(web.lastBody,"E_OTA_END") && Update.aborted && !ESP.restarted);
  Update=FakeUpdate(); Update.failEnd=true; sendImage(image); CHECK(web.lastCode==409 && has(web.lastBody,"E_OTA_END") && Update.aborted && !ESP.restarted);
  spin(1500); CHECK(link.ready && !systemFault); // a failed upload must not leave a spurious link fault behind
  Update=FakeUpdate(); planner.paused=false; sendImage(image);
  CHECK(web.lastCode==200 && has(web.lastBody,"\"ok\":true") && Update.ended && Update.data==image && ESP.restarted && planner.paused);
  uint32_t generationBefore=store.saved.generation; planner.invalidate(); restoreActive=false; planner.config.offset=300;
  nvsWriteFailure=true; commandLine("save_config"); spin(1000); CHECK(contains("E_NVS") && systemFault);
  CHECK(store.saved.generation==generationBefore); nvsWriteFailure=false;
  Serial.output.clear(); status(0,false);
  size_t start=0; unsigned parts=0;
  while(start<Serial.output.size()) { size_t end=Serial.output.find('\n',start); CHECK(end!=std::string::npos && end-start<=512); std::string line=Serial.output.substr(start,end-start); cJSON* j=cJSON_Parse(line.c_str()); CHECK(j); cJSON_Delete(j); start=end+1; ++parts; }
  CHECK(parts==3);
  // Indication sender is paced by confirmations and emits minimum-MTU chunks intact.
  peer=1; authenticated=true; subscribed=true; ++connectionEpoch;
  output("{\"hello\":\"繁體中文\"}\n",true); spin(100); CHECK(fakeIndications=="{\"hello\":\"繁體中文\"}\n");
  // Security gate is exercised through the actual callback, before request parsing.
  NimBLECharacteristic incoming; NimBLEConnInfo connection;
  incoming.value=request("get_status")+"\n";
  authenticated=false; subscribed=true;
  static_cast<NimBLECharacteristicCallbacks&>(rxCallbacks).onWrite(&incoming,connection);
  CHECK(rxQueue->items.empty());
  authenticated=true; subscribed=false;
  static_cast<NimBLECharacteristicCallbacks&>(rxCallbacks).onWrite(&incoming,connection);
  CHECK(rxQueue->items.empty());
  subscribed=true; fakeIndications.clear();
  for(size_t offset=0;offset<incoming.value.size();) {
    std::string chunk=incoming.value.substr(offset,20); offset+=chunk.size();
    NimBLECharacteristic piece; piece.value=chunk;
    static_cast<NimBLECharacteristicCallbacks&>(rxCallbacks).onWrite(&piece,connection); spin(2);
  }
  spin(300); CHECK(fakeIndications.find("\"part\":3")!=std::string::npos);
  connection.auth=false;
  static_cast<NimBLEServerCallbacks&>(serverCallbacks).onAuthenticationComplete(connection);
  CHECK(!authenticated.load());
  printf("PASS app: %u checks; actual command/supervisor/RTC/NVS/link code with simulated devices\n",checks);
  return 0;
}
