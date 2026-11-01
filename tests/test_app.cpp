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
  CHECK(!motor.running() && motor.m.mask==0 && !planner.position && planner.paused);
  for(uint8_t pin:{12,13,14,15}) CHECK(fakePinModes[pin]==OUTPUT && !fakePins[pin]);
  CHECK(!rtc.valid && !systemFault); // no RTC: the clock has no time until the first network time arrives
  { int64_t first=1793462400LL; xQueueOverwrite(syncQueue,&first); spin(500);
    CHECK(rtc.valid && rtc.utc>=first && !strcmp(source,"sntp") && !pendingSync && planner.paused); }
  commandLine("resume",",\"plan_id\":1"); CHECK(contains("E_PLAN_STALE")); CHECK(motor.m.moves==0);
  commandLine("jog_steps",",\"steps\":-1"); CHECK(contains("E_REVERSE_DISABLED"));
  commandLine("set_config",",\"values\":{\"mechanics_confirmed\":true,\"steps_per_page_u6\":136533333,\"cycle_minutes\":720}");
  CHECK(contains("completed") && planner.config.mechanics && store.dirty);
  commandLine("set_config",",\"values\":{\"max_step_rate\":1001}"); CHECK(contains("E_RANGE") && planner.config.rate==200);
  commandLine("set_config",",\"values\":{\"acceleration\":4001}"); CHECK(contains("E_RANGE") && planner.config.accel==100);
  commandLine("set_display",",\"hour\":8,\"minute\":0,\"aligned\":true"); CHECK(planner.position && planner.display==480);
  std::string jog=request("jog_steps",",\"steps\":4"); Serial.output.clear(); process(jog.c_str(),false); spin(2500);
  CHECK(contains("steps_sent\":4") && !planner.position && motor.m.executed==4 && !motor.m.mask);
  uint32_t accepts=motor.m.moves;
  Serial.output.clear(); process(jog.c_str(),false); spin(200); CHECK(motor.m.moves==accepts && contains("completed"));
  std::string reuse=jog; reuse[reuse.find("steps\":4")+7]='5'; process(reuse.c_str(),false); CHECK(contains("E_ID_REUSE") && motor.m.moves==accepts);
  commandLine("set_display",",\"hour\":8,\"minute\":0,\"aligned\":true");
  commandLine("advance_pages",",\"pages\":2"); spin(7000);
  CHECK(planner.display==482 && planner.remainder==66666 && !jobSeq && !motor.running());
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
  commandLine("set_time",",\"utc_s\":1793462400"); CHECK(contains("completed") && !strcmp(source,"ble_manual"));
  int64_t proposed=1793466000LL; xQueueOverwrite(syncQueue,&proposed); spin(500); // phone time is only a fallback: network time still applies
  CHECK(pendingSync==proposed && pendingSyncConfirm_ && planner.paused);
  commandLine("confirm_time",",\"utc_s\":1793466000"); CHECK(!pendingSync && !strcmp(source,"sntp"));
  commandLine("advance_pages",",\"pages\":5"); spin(200);
  commandLine("pause"); spin(9000); CHECK(!jobSeq && !manualPages && planner.position && !motor.running()); // pause lets the whole continuous move finish
  commandLine("advance_pages",",\"pages\":1"); spin(350); CHECK(jobSeq);
  commandLine("stop"); spin(500); CHECK(!planner.position && !motor.running() && !motor.m.mask && contains("coil_outputs_zero\":true"));
  commandLine("set_display",",\"hour\":9,\"minute\":0,\"aligned\":true");
  commandLine("advance_pages",",\"pages\":1"); spin(300); CHECK(motor.running()); motor.fail(); spin(300);
  CHECK(systemFault && !planner.position && !motor.running() && !motor.m.mask && !fakePins[12] && !fakePins[13] && !fakePins[14] && !fakePins[15]);
  commandLine("advance_pages",",\"pages\":1"); CHECK(contains("E_FAULT"));
  commandLine("clear_fault"); spin(100); CHECK(!systemFault && !motor.faulted() && !planner.position);
  // A move that never finishes is cut off by the timeout, with the coils released.
  { uint32_t t=fakeMs; CHECK(motor.start(50,10,1,200,t)); spin(300); CHECK(motor.faulted() && !motor.m.mask && !fakePins[12] && !fakePins[13] && !fakePins[14] && !fakePins[15]);
    spin(10); CHECK(systemFault); commandLine("clear_fault"); spin(100); CHECK(!systemFault); }
  // ---- Web console: authenticated, same protocol, client-supplied ids ignored ----
  auto webCmd=[](const char* body) { web.body=body; web.post["/api/cmd"](); return web.lastBody; };
  auto has=[](const std::string& s,const char* needle) { return s.find(needle)!=std::string::npos; };
  CHECK(WiFi.apName.rfind("FlipClock-",0)==0 && strlen(webPassword)==12 && WiFi.apPassword==webPassword && web.begun);
  CHECK(fakeNvs["flip-web"]["pw"].size()==13);
  web.get["/"](); CHECK(web.lastCode==200 && has(web.lastBody,"翻頁時鐘") && has(web.lastType,"text/html"));
  web.bearer=std::string("Bearer ")+webToken; CHECK(strlen(webToken)==32 && fakeNvs["flip-web"]["tok"].size()==33);
  web.authOk=false; web.get["/api/state"](); CHECK(web.lastCode==401 && !has(web.lastBody,"display"));
  uint32_t accepted=motor.m.moves; web.body="{\"op\":\"jog_steps\",\"steps\":4}"; web.post["/api/cmd"]();
  CHECK(web.lastCode==401 && motor.m.moves==accepted && !queuedJog_); web.authOk=true;
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
  spin(14000); CHECK(planner.display==486 && !motor.running() && !motor.m.mask && !largeConfirmed_ && !systemFault);
  CHECK(savedDisplay==486 && store.saved.display==486 && !planner.paused && !largeRequired);
  // Any deliberate action cancels a pending restore, and an unconfirmed-mechanics snapshot is never restored.
  commandLine("pause"); spin(500); restoreActive=false;
  planner=Planner(); planner.config=persisted; Saved untrusted=store.saved; untrusted.config.mechanics=false;
  Saved keep=store.saved; store.saved=untrusted; CHECK(!restoreSnapshot() && !planner.position); store.saved=keep;
  planner.config=persisted; CHECK(restoreSnapshot() && restoreActive); commandLine("pause"); CHECK(!restoreActive);
  { // Cold boot without an RTC: the position is restored but nothing moves until network time arrives.
    int64_t keepUtc=rtc.utc; rtc=NetClock(); planner=Planner(); planner.config=persisted; spin(300); commandLine("pause");
    CHECK(restoreSnapshot() && restoreActive); spin(1500);
    CHECK(restoreActive && planner.paused && !jobSeq && !motor.running() && !rtc.valid);
    xQueueOverwrite(syncQueue,&keepUtc); spin(500); CHECK(rtc.valid && !restoreActive); commandLine("pause"); spin(6000);
  }
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
    CHECK(!NimBLEDevice::getAdvertising()->on);  // BLE stays quiet during the attempt
    { int begins=WiFi.begins; WiFi.fireDisconnect(8); spin(16000); CHECK(WiFi.begins==begins); // our own disconnect is not a failure
      WiFi.fireDisconnect(15); CHECK(has(getWifi(),"\"why\":15")); spin(100); CHECK(WiFi.begins==begins+1); // a real failure retries; the cause is reported
      WiFi.fireDisconnect(15); spin(30000); }
    json=getWifi(); CHECK(has(json,"E_WIFI_TIMEOUT") && has(json,"\"why\":15") && !network.ssid[0] && NimBLEDevice::getAdvertising()->on);
    // The connection comes up after the trial gave up: it is kept, so it survives a power cycle.
    WiFi.begin("Home","right-password"); WiFi.state=WL_CONNECTED; spin(10); CHECK(!strcmp(network.ssid,"Home"));
    { Network live=network; network=Network(); loadNetwork(); CHECK(!strcmp(network.ssid,"Home") && !strcmp(network.password,"right-password")); network=live; }
    WiFi.disconnect(); network=Network(); CHECK(saveNetwork());
    // Verified connection: saved, persisted across a reload, password cleared from RAM trial buffer.
    postWifi("{\"op\":\"connect\",\"ssid\":\"Home\",\"password\":\"right-password\"}"); WiFi.state=WL_CONNECTED; spin(200);
    json=getWifi(); CHECK(has(json,"\"state\":\"ok\"") && has(json,"192.168.1.77") && has(json,"\"connected\":true") && has(json,"\"saved\":\"Home\"") && !trialPassword[0]);
    { Network live=network; network=Network(); loadNetwork(); CHECK(!strcmp(network.ssid,"Home") && !strcmp(network.password,"right-password")); network=live; }
    // Power cycle: the saved network is joined with no help, and retries stay frequent while the router boots.
    WiFi.state=WL_DISCONNECTED; WiFi.beganSsid.clear(); WiFi.beganPassword.clear(); network=Network(); loadNetwork(); lastWifi=fakeMs-300000; wifiBackoff=30000; spin(10);
    CHECK(WiFi.beganSsid=="Home" && WiFi.beganPassword=="right-password");
    spin(200000); CHECK(wifiBackoff==60000 && uint32_t(fakeMs-lastWifi)<=60000);
    WiFi.state=WL_CONNECTED; spin(10); WiFi.state=WL_DISCONNECTED; wifiBackoff=30000;
    // A failed attempt on another network goes back to the saved one.
    postWifi("{\"op\":\"connect\",\"ssid\":\"Other\",\"password\":\"other-password\"}"); WiFi.state=WL_NO_SSID_AVAIL; spin(3500);
    json=getWifi(); CHECK(has(json,"E_WIFI_NOT_FOUND") && !strcmp(network.ssid,"Home") && WiFi.beganSsid=="Home" && !strcmp(network.password,"right-password"));
    // Connected but the save fails: reported as failure, old credentials kept.
    WiFi.state=WL_DISCONNECTED; postWifi("{\"op\":\"connect\",\"ssid\":\"New\",\"password\":\"new-password1\"}"); WiFi.state=WL_CONNECTED;
    nvsWriteFailure=true; spin(200); nvsWriteFailure=false; json=getWifi(); CHECK(has(json,"E_WIFI_SAVE") && !strcmp(network.ssid,"Home"));
    // Forget.
    CHECK(has(postWifi("{\"op\":\"forget\"}"),"\"ok\":true") && !network.ssid[0] && WiFi.disconnected);
    WiFi.begin("Home","right-password"); WiFi.state=WL_CONNECTED; spin(10); CHECK(!network.ssid[0]); WiFi.disconnect(); // a connection still going down is not re-saved
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
    planner.paused=true; spin(4000); CHECK(!motor.running() && !jobSeq); // let any earlier catch-up finish and disarm
    planner.paused=false; planner.position=true; planner.display=target(rtc.utc,planner.config); lastCheckpoint=fakeMs-uint32_t(planner.config.checkpoint)*60000UL-1;
    spin(1); CHECK(savePending && planner.paused); // checkpoint save has started, not yet finished
    commandLine("pause"); spin(1500); CHECK(!savePending && planner.paused); // pause during the save is kept
    planner.paused=false; lastCheckpoint=fakeMs-uint32_t(planner.config.checkpoint)*60000UL-1; savedDisplay=-1;
    spin(1); CHECK(savePending); planner.changed(false); spin(1500); CHECK(!savePending && planner.paused); // so is any other planner change
    planner.paused=false; savedDisplay=int32_t(planner.display); lastCheckpoint=fakeMs-uint32_t(planner.config.checkpoint)*60000UL-1;
    spin(1500); CHECK(!savePending && !planner.paused); // an undisturbed save still resumes the running clock
    planner.paused=true;
  }
  // ---- Software clock (no RTC chip): invalid until written, then counted from millis(), wrap-safe ----
  {
    NetClock c; CHECK(!c.read(0) && !c.valid && !c.write(5,0) && !c.valid);
    CHECK(c.write(1800000000LL,1000) && c.valid && c.utc==1800000000LL);
    CHECK(c.read(3500) && c.utc==1800000002LL && c.read(3999) && c.utc==1800000002LL && c.read(4000) && c.utc==1800000003LL);
    uint32_t wrapAt=0xFFFFFF00u; NetClock w; CHECK(w.write(1800000000LL,wrapAt));
    CHECK(w.read(wrapAt+5000u) && w.utc==1800000005LL && w.read(wrapAt+9000u) && w.utc==1800000009LL);
  }  // ---- Web login: password gets the permanent token; repeated failures lock out for 30 s ----
  {
    auto login=[&](const std::string& pw) { web.body="{\"password\":\""+pw+"\"}"; web.post["/api/login"](); return web.lastCode; };
    std::string pw=webPassword; web.authOk=false; // login itself needs no token
    CHECK(login("wrong-password")==401 && !has(web.lastBody,webToken));
    CHECK(login(pw)==200 && has(web.lastBody,webToken));
    for(int i=0;i<5;++i) CHECK(login("wrong-password")==401);
    CHECK(login(pw)==429 && !has(web.lastBody,webToken));
    spin(31000); CHECK(login(pw)==200); web.authOk=true;
    // ---- Password change: old one required, replaces the token and the hotspot password, survives a reboot ----
    auto change=[&](const std::string& o,const std::string& n) { web.body="{\"old\":\""+o+"\",\"new\":\""+n+"\"}"; web.post["/api/password"](); return web.lastBody; };
    std::string token=webToken;
    CHECK(has(change("nope","new-pass-123"),"E_WRONG") && pw==webPassword && token==webToken);
    CHECK(has(change(pw,"short"),"E_PASSWORD") && has(change(pw,"中文密碼不可以用"),"E_PASSWORD") && pw==webPassword);
    nvsWriteFailure=true; CHECK(has(change(pw,"new-pass-123"),"E_NVS") && pw==webPassword && token==webToken); nvsWriteFailure=false;
    CHECK(has(change(pw,"new-pass-123"),"\"ok\":true") && !strcmp(webPassword,"new-pass-123") && token!=webToken && has(web.lastBody,webToken));
    web.get["/api/state"](); CHECK(web.lastCode==401); // every other browser is logged out
    web.bearer=std::string("Bearer ")+webToken; web.get["/api/state"](); CHECK(web.lastCode==200);
    spin(2000); CHECK(WiFi.apPassword=="new-pass-123");
    token=webToken; webPassword[0]=0; webToken[0]=0; loadWebPassword(); CHECK(!strcmp(webPassword,"new-pass-123") && token==webToken);
  }
  // ---- Step offset: moves the motor but keeps the position; only forward, so a smaller value wraps through one page ----
  {
    commandLine("pause"); spin(6000); commandLine("set_display",",\"hour\":8,\"minute\":0,\"aligned\":true"); CHECK(planner.position && planner.display==480);
    int startTrim=planner.config.trim; CHECK(startTrim==0);
    commandLine("set_trim",",\"steps\":20"); spin(3000);
    CHECK(contains("\"trim\":20") && planner.config.trim==20 && motor.m.executed==20 && planner.position && planner.display==480 && planner.remainder==0 && store.dirty);
    uint32_t page=0,next=0; CHECK(pageSteps(planner.config.q,planner.remainder,1,page,next));
    commandLine("set_trim",",\"steps\":5"); spin(6000);
    CHECK(planner.config.trim==5 && motor.m.executed==int32_t(page)-15 && planner.position && planner.display==481 && planner.remainder==next);
    uint32_t accepts=motor.m.moves; commandLine("set_trim",",\"steps\":5"); spin(100); CHECK(contains("completed") && motor.m.moves==accepts); // nothing to do
    commandLine("set_trim",",\"steps\":300"); CHECK(contains("E_TRIM") && planner.config.trim==5);
    commandLine("set_trim",",\"steps\":1001"); CHECK(contains("E_RANGE"));
    commandLine("set_display",",\"hour\":8,\"minute\":0,\"aligned\":true"); CHECK(planner.config.trim==5); // re-zeroing keeps the offset
    spin(6000); commandLine("save_config"); spin(500); CHECK(contains("persisted\":true") && store.saved.config.trim==5 && !store.dirty);
    Store reboot; Config loaded; CHECK(reboot.begin(loaded) && loaded.trim==5);
    commandLine("set_trim",",\"steps\":-3"); spin(6000); CHECK(planner.config.trim==-3 && planner.position);
    spin(6000); commandLine("save_config"); spin(500); Store reboot2; Config loaded2; CHECK(reboot2.begin(loaded2) && loaded2.trim==-3);
    planner.invalidate(); commandLine("set_trim",",\"steps\":1"); CHECK(contains("E_NOT_CALIBRATED"));
    commandLine("set_display",",\"hour\":8,\"minute\":0,\"aligned\":true");
  }
  // ---- Wizard end to end without Wi-Fi: phone time, zero at the current time, verify N minutes, save, resume ----
  {
    commandLine("pause"); spin(3000); int64_t phone=rtc.utc-rtc.utc%60+5; commandLine("set_time",(",\"utc_s\":"+std::to_string(phone)).c_str());
    uint16_t now0=target(phone,planner.config);
    commandLine("set_display",(",\"hour\":"+std::to_string(now0/60)+",\"minute\":"+std::to_string(now0%60)+",\"aligned\":true").c_str());
    commandLine("advance_pages",",\"pages\":10"); spin(12000); CHECK(planner.display==uint16_t((now0+10)%720));
    spin(6000); commandLine("save_config"); spin(500); CHECK(contains("persisted\":true"));
    commandLine("preview_sync"); CHECK(contains("plan_id") && contains("\"pages\":0"));
    char plan[80]; snprintf(plan,sizeof(plan),",\"plan_id\":%u,\"confirm_large\":true",planner.preview.id); commandLine("resume",plan); CHECK(contains("completed") && !planner.paused);
    uint32_t moves=motor.m.moves; spin(30000); CHECK(motor.m.moves==moves && !planner.paused && planner.display==uint16_t((now0+10)%720)); // ahead of the time: it waits
    web.get["/api/state"](); CHECK(has(web.lastBody,"\"ahead\":10") || has(web.lastBody,"\"ahead\":9"));
    CHECK(!strlen(lastError));
    spin(14*60000); CHECK(motor.m.moves>moves && planner.display==target(rtc.utc,planner.config) && !planner.paused); // and walks once the time catches up
    web.get["/api/state"](); CHECK(has(web.lastBody,"\"ahead\":0"));
    commandLine("pause"); spin(3000);
  }
  // ---- Fast zeroing: many pages are ONE continuous move (ramp up, cruise, ramp down), not one move per page ----
  commandLine("set_config",",\"values\":{\"max_step_rate\":500,\"acceleration\":3000}");
  CHECK(contains("completed") && planner.config.rate==500 && planner.config.accel==3000);
  {
    uint16_t d0=planner.display; uint32_t moves=motor.m.moves,t0=fakeMs; CHECK(planner.position);
    commandLine("advance_pages",",\"pages\":100"); CHECK(contains("accepted"));
    spin(34000);
    CHECK(!jobSeq && !manualPages && planner.display==uint16_t((d0+100)%720) && !motor.running() && manualCompleted_==100);
    CHECK(motor.m.moves-moves==2 && fakeMs-t0<40000); // 65 + 35 pages; the per-page profile needed ~4 minutes
    commandLine("advance_pages",",\"pages\":721"); CHECK(contains("E_RANGE"));
    commandLine("jog_steps",",\"steps\":2000"); spin(8000); CHECK(!jobSeq && !queuedJog_ && motor.m.executed==2000 && !motor.m.mask);
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
  std::string bad(70000,'x'); sendImage(bad); CHECK(web.lastCode==409 && has(web.lastBody,"E_OTA_IMAGE") && Update.aborted && Update.data.empty() && !ESP.restarted);
  Update=FakeUpdate(); Update.failBegin=true; sendImage(image); CHECK(web.lastCode==409 && has(web.lastBody,"E_OTA_NO_PARTITION") && !ESP.restarted);
  Update=FakeUpdate(); std::string tiny(100,'x'); tiny[0]=char(0xE9); sendImage(tiny); CHECK(web.lastCode==409 && has(web.lastBody,"E_OTA_END") && Update.aborted && !ESP.restarted);
  Update=FakeUpdate(); Update.failEnd=true; sendImage(image); CHECK(web.lastCode==409 && has(web.lastBody,"E_OTA_END") && Update.aborted && !ESP.restarted);
  spin(1500); CHECK(!systemFault); // a failed upload must not leave a fault behind
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
  printf("PASS app: %u checks; actual command/supervisor/motor/NVS/web code with simulated devices\n",checks);
  return 0;
}
