// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <Arduino.h>
// Single-page commissioning UI. All behaviour is decided by the firmware; this page only issues
// the same protocol operations as BLE and polls /api/state.
static const char WEB_PAGE[] PROGMEM = R"HTML(<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>翻頁時鐘</title>
<style>
:root{--bg:#f4f5f7;--fg:#1c2330;--card:#fff;--line:#d5d9e0;--acc:#0b63ce;--bad:#b3261e;--ok:#1a7f37;--mut:#5f6b7a}
@media(prefers-color-scheme:dark){:root{--bg:#12161c;--fg:#e8ecf2;--card:#1b222b;--line:#2f3a48;--acc:#5aa2ff;--bad:#ff8a80;--ok:#65d17f;--mut:#9aa7b8}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,"Noto Sans TC",sans-serif}
main{max-width:640px;margin:0 auto;padding:12px 16px 80px}h1{font-size:20px;margin:12px 0}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:12px 0}
h2{font-size:16px;margin:0 0 6px}p{margin:6px 0;color:var(--mut);font-size:14px}
.big{font-size:40px;font-weight:700;letter-spacing:1px}.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}
button{font:inherit;padding:9px 14px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
button.p{background:var(--acc);border-color:var(--acc);color:#fff}button.d{background:var(--bad);border-color:var(--bad);color:#fff}
button:disabled{opacity:.4}input{font:inherit;width:78px;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}
dl{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;margin:6px 0;font-size:14px}dt{color:var(--mut)}dd{margin:0}
#msg{position:fixed;left:0;right:0;bottom:0;padding:12px 16px;background:var(--card);border-top:2px solid var(--line);font-size:15px}
#msg.bad{border-color:var(--bad);color:var(--bad)}#msg.ok{border-color:var(--ok)}
.t{border-top:1px solid var(--line);padding:8px 0}.pass{color:var(--ok)}
input.w{width:100%}input.m{width:130px}summary{cursor:pointer;margin:6px 0;font-size:14px}[hidden]{display:none!important}.err{color:var(--bad);min-height:1.5em}
</style></head><body>
<main id="login" hidden><h1>翻頁時鐘</h1><section><h2>登入</h2><p>密碼和時鐘熱點的 Wi-Fi 密碼相同。登入後這個瀏覽器會一直記住，不用再輸入。</p>
<form onsubmit="login();return false"><div class="row"><input id="lpw" class="w" type="password" placeholder="密碼" autocomplete="current-password"></div>
<div class="row"><button class="p" id="bLogin">登入</button></div><p class="err" id="lerr"></p></form></section></main>
<main id="app" hidden>
<h1>翻頁時鐘 <small id="badge"></small></h1>
<section><div class="big" id="disp">--:--</div>
<dl><dt>狀態</dt><dd id="st"></dd><dt>目前時間</dt><dd id="rt"></dd>
<dt>位置記憶</dt><dd id="ps"></dd><dt>已儲存</dt><dd id="sv"></dd></dl>
<div id="banner"></div>
<div class="row"><button id="bPause" onclick="act(pause)">暫停走時</button>
<button class="d" id="bStop" onclick="stopNow()">緊急停止</button><button id="bClear" onclick="act(clearFault)">清除故障</button></div></section>

<section><h2>1. 校時（網路時間）</h2><p>時鐘沒有電池 RTC，每次開機都靠 Wi-Fi 的網路時間（NTP）校時，連上網路後自動完成。請先在最下面的「Wi-Fi 連線」連上家中網路。沒有網路時，可暫時用手機時間（斷電後會消失）。</p>
<div class="row"><button id="bTime" onclick="act(timeSync)">暫時用手機時間</button><button onclick="act(tzSync)">時區設為手機時區</button></div></section>

<section><h2>2. 歸零</h2><p>輸入時鐘<b>現在顯示</b>的時間，馬達不會轉動。</p>
<div class="row">目前顯示 <input id="ah" type="number" min="1" max="12" value="12"> : <input id="am" type="number" min="0" max="59" value="0">
<button class="p" id="bZero" onclick="act(zero)">以此歸零</button></div>
<details><summary>進階：步數與速度</summary>
<div class="row">每分鐘步數 <input id="q" class="m" type="number" step="0.000001" value="136.533333"></div>
<div class="row">速度 <input id="rate" type="number" min="10" max="1000" value="900"> 步/秒　加速度 <input id="accel" type="number" min="1" max="4000" value="400"> 步/秒²</div>
<p>預設值來自原作者設定：半步模式 4096 ÷ 30 = 136.533 步/分鐘，速度 900、加速度 400。馬達只嗡嗡響或漏步時請調低。修改後按「以此歸零」生效。</p></details></section>

<section><h2>3. 步數偏移</h2><p>調整馬達每分鐘停下的位置，讓翻片確實翻過去。翻頁太晚或沒翻就加大，太早就減小。這個值會一直保留到下次調整，重新歸零也不會清除。</p>
<p id="trimNow"></p>
<div class="row"><button class="tq" onclick="nudge(-8)">−8</button><button class="tq" onclick="nudge(-1)">−1</button><button class="tq" onclick="nudge(1)">+1</button><button class="tq" onclick="nudge(8)">+8</button></div>
<div class="row">偏移值 <input id="trim" type="number" value="0"> 步 <button id="bTrim" onclick="act(()=>setTrim(+$('trim').value))">套用</button></div>
<p>馬達只能正轉，所以減小偏移時會往前轉接近一分鐘的距離，時鐘可能多翻一頁，韌體會自動記下。</p></section>

<section><h2>4. 驗證</h2><p>前進任意分鐘數，再對照時鐘顯示。可重複操作。</p>
<div class="row"><input id="vm" type="number" min="1" max="720" value="10"> 分鐘 <button class="p" id="bVerify" onclick="act(()=>verify(+$('vm').value))">前進</button>
<button class="tq" onclick="act(()=>verify(1))">1 分鐘</button><button class="tq" onclick="act(()=>verify(60))">1 小時</button></div>
<div id="vres"></div></section>

<section><h2>5. 儲存</h2><p>滿意後儲存。偏移值與位置會永久保留，斷電重啟後自動補跑到目前時間。</p>
<div class="row"><button class="p" id="bFinish" onclick="act(finish)">儲存並開始走時</button><button id="bSave" onclick="act(saveOnly)">只儲存偏移值</button></div></section>
<section id="wifi"><h2>Wi-Fi 連線</h2><p>連上家中 Wi-Fi 才能取得網路時間（每 6 小時校正一次，誤差小於 5 分鐘不會中斷走時）。掃描與測試連線時，這個熱點可能中斷約 10–20 秒，頁面會自動重新連線。</p>
<dl><dt>目前</dt><dd id="wst">--</dd></dl>
<div id="wlan" hidden style="border:2px solid #2a9d4b;border-radius:8px;padding:10px;margin:8px 0"></div>
<div class="row"><button id="bScan" onclick="wifiScan()">掃描附近 Wi-Fi</button></div>
<p style="font-size:.85em;opacity:.8">注意：ESP32 只支援 2.4 GHz，看不到 5 GHz 的網路；掃不到時可直接在下方手動輸入名稱（大小寫要相同）。</p>
<div id="wnets"></div>
<div class="row"><input id="wss" placeholder="Wi-Fi 名稱" style="width:100%" autocomplete="off"></div>
<div class="row"><input id="wpw" type="password" placeholder="密碼（開放網路留空）" style="width:100%" autocomplete="off"></div>
<div class="row"><button class="p" id="bConn" onclick="wifiConnect()">測試連線並儲存</button><button id="bForget" onclick="wifiForget()">忘記已儲存的網路</button></div>
</section>

<section><h2>更改密碼</h2><p>這組密碼同時是網頁登入密碼和時鐘熱點的 Wi-Fi 密碼。忘記時可從 UART 輸入 <code>access</code> 查看。</p>
<div class="row"><input id="pold" class="w" type="password" placeholder="目前密碼" autocomplete="current-password"></div>
<div class="row"><input id="pnew" class="w" type="password" placeholder="新密碼（8–63 個英數字或符號）" autocomplete="new-password"></div>
<div class="row"><input id="pnew2" class="w" type="password" placeholder="再輸入一次新密碼" autocomplete="new-password"></div>
<div class="row"><button class="p" onclick="act(changePassword)">更改密碼</button><button onclick="setToken('')">登出這個瀏覽器</button></div></section>

<section><h2>韌體更新（OTA）</h2><p>選擇 <b>esp32_clock.ino.bin</b>。更新前會自動暫停走時；更新完成後裝置重新啟動，位置與設定都保留。更新期間請勿斷電。</p>
<div class="row"><input type="file" id="fw" accept=".bin" style="width:auto"><button class="d" onclick="ota()">上傳並更新</button></div></section>
</main><div id="msg" class="ok" hidden>連線中…</div>
<script>
const $=i=>document.getElementById(i),pad=n=>String(n).padStart(2,'0');
const E={E_BUSY:'裝置忙碌，請先按「暫停走時」並等動作結束',E_TIME_INVALID:'尚無有效時間：請先連上 Wi-Fi 取得網路時間，或暫時用手機時間',E_MOTOR_TIMEOUT:'馬達轉動逾時，位置未知，請清除故障後重新歸零',
E_NOT_CALIBRATED:'尚未歸零，請先完成步驟 2',E_RANGE:'數值超出範圍',E_FAULT:'系統故障，請先按「清除故障」',E_PLAN_STALE:'預覽已過期，請重試',
E_REVERSE_DISABLED:'目前只支援正向轉動',E_SAVE_THROTTLED:'5 秒內不能重複儲存，請稍後再試',E_NVS:'儲存失敗',
E_OTA_NO_PARTITION:'此韌體的分割表沒有 OTA 分區，需先用 UART 燒錄一次',E_OTA_IMAGE:'不是有效的 ESP32 韌體檔',E_OTA_WRITE:'寫入 Flash 失敗',
E_OTA_END:'映像驗證失敗',E_AUTH:'未授權',E_TRIM:'偏移調整幅度太大，一次請勿超過一分鐘的步數'};
const ST={IDLE:'待命（自動走時中）',PAUSED:'已暫停',MOVING:'換頁中',NEEDS_TIME:'等待網路時間（請連上 Wi-Fi）',NEEDS_CALIBRATION:'需要歸零',
NEEDS_CATCHUP_CONFIRM:'需要確認補跑',FAULT:'故障'};
let S={},busyUi=false,V=null,lastV='',filled=false,TOKEN='';
try{TOKEN=localStorage.getItem('flipToken')||''}catch(e){}
function setToken(t){TOKEN=t;try{if(t)localStorage.setItem('flipToken',t);else localStorage.removeItem('flipToken')}catch(e){}if(!t)showLogin(true)}
async function F(u,o){o=Object.assign({},o);o.headers={Authorization:'Bearer '+TOKEN};const r=await fetch(u,o);if(r.status==401){setToken('');throw new Error('請重新登入')}return r}
const fmt=(i,c)=>{c=c||S.cycle||720;const h=Math.floor(i/60);return(c==720?(h%12||12):pad(h))+':'+pad(i%60)};
const say=(t,bad)=>{const e=$('msg');e.textContent=t;e.className=bad?'bad':'ok'};
async function api(op,a){const r=await F('/api/cmd',{method:'POST',body:JSON.stringify(Object.assign({op},a||{}))});
let j={phase:'error',code:'E_EMPTY'};for(const l of (await r.text()).trim().split('\n')){try{j=JSON.parse(l)}catch(e){}}return j}
async function run(op,a){const j=await api(op,a);if(j.phase=='error')throw new Error((E[j.code]||'失敗')+'（'+j.code+'）');return j}
async function refresh(){S=await(await F('/api/state')).json();render()}
async function idle(ms){const t=Date.now();for(;;){await new Promise(r=>setTimeout(r,500));await refresh();if(!S.busy)return;if(Date.now()-t>ms)throw new Error('等待逾時')}}
async function act(fn){if(busyUi)return;busyUi=true;render();try{await fn()}catch(e){say(e.message,1)}busyUi=false;try{await refresh()}catch(e){}}
async function pause(){await run('pause');await idle(30000);say('已暫停')}
async function stopNow(){try{await run('stop');say('已停止馬達，位置需重新確認',1)}catch(e){say(e.message,1)}}
async function clearFault(){await run('clear_fault');await idle(15000);say('已清除故障，請重新確認顯示位置')}
async function timeSync(){await ensurePaused();const off=-new Date().getTimezoneOffset();await run('set_config',{values:{utc_offset_min:off}});
await run('set_time',{utc_s:Math.floor(Date.now()/1000)});say('已暫時用手機時間校時（UTC'+(off>=0?'+':'')+off/60+'），連上 Wi-Fi 後會改用網路時間。請按「儲存並開始走時」')}
async function tzSync(){await ensurePaused();const off=-new Date().getTimezoneOffset();await run('set_config',{values:{utc_offset_min:off}});say('時區已設為 UTC'+(off>=0?'+':'')+off/60+'。請按「儲存並開始走時」')}
async function ensurePaused(){await refresh();if(!S.paused||S.busy){say('先暫停走時…');await run('pause');await idle(60000)}}
async function zero(){const h=+$('ah').value,m=+$('am').value,q=Math.round(parseFloat($('q').value)*1e6),r=+$('rate').value,a=+$('accel').value;
if(!(h>=1&&h<=12&&m>=0&&m<=59&&q>0))throw new Error('時間或每分鐘步數不正確');
if(!(r>=10&&r<=1000&&a>=1&&a<=4000))throw new Error('速度需為 10–1000，加速度需為 1–4000');
await ensurePaused();await run('set_config',{values:{mechanics_confirmed:true,cycle_minutes:720,steps_per_page_u6:q,max_step_rate:r,acceleration:a}});
await run('set_display',{hour:h%12,minute:m,aligned:true});V=null;say('已記住目前顯示 '+h+':'+pad(m)+'。馬達沒有轉動。')}
async function setTrim(v){if(!Number.isInteger(v))throw new Error('偏移值需為整數');await ensurePaused();say('調整偏移中…');
await run('set_trim',{steps:v});await idle(60000);if(!S.pos)throw new Error('調整中斷，位置未知，請重新歸零');$('trim').value=S.trim;say('偏移已設為 '+S.trim+' 步，可以前進幾分鐘驗證。滿意後記得儲存')}
function nudge(d){act(()=>setTrim(S.trim+d))}
async function verify(n){if(!Number.isInteger(n)||n<1||n>720)throw new Error('分鐘數需為 1–720');await ensurePaused();const from=S.display;
say('前進 '+n+' 分鐘…');await run('advance_pages',{pages:n});await idle(600000);
if(!S.pos||S.display!=(from+n)%S.cycle)throw new Error('換頁中斷，位置未知，請重新歸零');V={from,to:S.display,n};say('請對照時鐘實際顯示')}
async function saveOnly(){await ensurePaused();await run('save_config');await idle(30000);if(S.dirty)throw new Error('儲存失敗，請稍候 5 秒再試');say('偏移值 '+S.trim+' 步已永久儲存')}
async function finish(){await ensurePaused();await run('set_config',{values:{mechanics_confirmed:true}});await run('save_config');await idle(30000);
if(S.dirty)throw new Error('儲存失敗，請稍候 5 秒再試');const p=await run('preview_sync');await run('resume',{plan_id:p.plan_id,confirm_large:true});
say('已儲存，正在補跑到目前時間，之後自動走時')}
const WE={E_WIFI_AUTH:'密碼錯誤或被拒絕',E_WIFI_NOT_FOUND:'找不到這個 Wi-Fi',E_WIFI_TIMEOUT:'連線逾時',E_WIFI_SAVE:'連上了但儲存失敗',
E_WIFI_SSID:'請輸入 Wi-Fi 名稱',E_WIFI_PASSWORD:'密碼需 8–64 個字元（開放網路請留空）',E_BUSY:'上一個操作還在進行中'};
let W={trial:{},networks:[]},wifiBusy=false;
async function wifiPost(o){const r=await F('/api/wifi',{method:'POST',body:JSON.stringify(o)});return r.json()}
async function wifiRefresh(){W=await(await F('/api/wifi')).json();renderWifi()}
function lanBox(){const s=W.sta||{},b=$('wlan');if(!s.connected||!s.ip){b.hidden=true;b.textContent='';b.dataset.k='';return}
const k=s.ip+'|'+s.host+'|'+W.saved+'|'+s.ssid;if(b.dataset.k===k)return;b.dataset.k=k;b.hidden=false;b.textContent='';
const add=(tag,text,st)=>{const e=document.createElement(tag);e.textContent=text;if(st)e.style.cssText=st;b.appendChild(e);return e};
const nm=s.ssid||W.saved;add('b','✅ 已連上「'+nm+'」'+(W.saved?'，並已儲存':'（尚未儲存，請再按一次「測試連線並儲存」）'));
add('p','之後從區網進入這個控制頁，不必再連時鐘的熱點。請先讓手機或電腦連到同一個 Wi-Fi「'+nm+'」，再開啟：','margin:6px 0');
const url='http://'+s.ip+'/',a=add('a',url,'font-size:1.3em;font-weight:bold;word-break:break-all');a.href=url;a.target='_blank';
const r=add('div','','margin:8px 0');const c=document.createElement('button');c.textContent='複製網址';c.onclick=async()=>{try{await navigator.clipboard.writeText(url);say('已複製 '+url)}catch(e){say('請長按網址複製：'+url)}};r.appendChild(c);
add('p','也可以試 http://'+(s.host||'flipclock.local')+'/（iPhone、Mac、Windows 通常可用，部分 Android 不行）。換網址要重新登入一次，密碼相同。網址若改變（路由器重新分配），回到時鐘熱點即可查看新網址。','font-size:.85em;opacity:.85;margin:4px 0')}
function renderWifi(){const s=W.sta||{};$('wst').textContent=s.connected?('已連線 '+(W.saved||'')+'　'+(s.ip||'')+'（'+s.rssi+' dBm）'):(W.saved?('已儲存「'+W.saved+'」，連線中…（分享器剛開機時可能要等幾分鐘）'):'未設定，斷電後不會自動連線');lanBox();
const box=$('wnets');if(box.dataset.k===JSON.stringify(W.networks)+W.scanning)return;box.dataset.k=JSON.stringify(W.networks)+W.scanning;box.textContent='';
if(W.scanning){const p=document.createElement('p');p.textContent='掃描中…';box.appendChild(p)}
for(const n of W.networks){const b=document.createElement('button');b.textContent=(n.open?'🔓 ':'🔒 ')+n.ssid+'  '+n.rssi+' dBm';b.style.margin='3px 6px 3px 0';
b.onclick=()=>{$('wss').value=n.ssid;$('wpw').value='';if(n.open)say('這是開放網路，密碼留空即可');else $('wpw').focus()};box.appendChild(b)}}
async function wifiWait(ms,done){const t=Date.now();while(Date.now()-t<ms){await new Promise(r=>setTimeout(r,1500));try{await wifiRefresh();if(done())return true}catch(e){}}return false}
async function wifiScan(){if(wifiBusy)return;wifiBusy=true;try{say('掃描中。時鐘的熱點會中斷約 10–30 秒，這是正常的：請等手機自動重連 FlipClock-… ，結果會自己出現',0);const j=await wifiPost({op:'scan'});if(!j.ok)throw new Error(WE[j.error]||j.error);
await wifiWait(60000,()=>!W.scanning&&W.scanned);say(W.networks.length?'找到 '+W.networks.length+' 個 Wi-Fi，點選後輸入密碼':(W.scanError?'掃描失敗（無線模組忙碌），請再按一次；或直接手動輸入名稱':'沒有掃到 Wi-Fi（只支援 2.4 GHz，請靠近分享器）；可直接手動輸入名稱'),!W.networks.length)}
catch(e){say(e.message,1)}wifiBusy=false}
async function wifiConnect(){if(wifiBusy)return;const ssid=$('wss').value.trim(),password=$('wpw').value;wifiBusy=true;
try{if(!ssid)throw new Error(WE.E_WIFI_SSID);say('測試連線中，最久約 45 秒。熱點會中斷，請等手機自動重連 FlipClock-…，結果會自己出現（不要重複按）');const j=await wifiPost({op:'connect',ssid,password});if(!j.ok)throw new Error(WE[j.error]||j.error);
const ok=await wifiWait(120000,()=>W.trial&&W.trial.state!='running');
if(!ok)throw new Error('等不到結果，請重新整理頁面確認');
if(W.trial.state=='ok'){$('wpw').value='';say('已連上「'+W.trial.ssid+'」並儲存。請看上方綠框的區網網址，讓手機連到同一個 Wi-Fi 後開啟');$('wlan').scrollIntoView({behavior:'smooth',block:'center'})}else throw new Error('連線失敗：'+(WE[W.trial.reason]||W.trial.reason)+'；未儲存，已恢復原本的連線')}
catch(e){say(e.message,1)}wifiBusy=false}
async function wifiForget(){if(wifiBusy||!confirm('忘記已儲存的 Wi-Fi？'))return;wifiBusy=true;try{const j=await wifiPost({op:'forget'});if(!j.ok)throw new Error(WE[j.error]||j.error);await wifiRefresh();say('已忘記 Wi-Fi')}catch(e){say(e.message,1)}wifiBusy=false}
async function confirmSync(){await run('confirm_time',{utc_s:S.syncUtc});say('已用網路時間校時，請按「儲存並開始走時」')}
let otaBusy=false;
function ota(){const f=$('fw').files[0];if(!f)return say('請先選擇 .bin 檔',1);
if(!confirm('更新韌體 '+f.name+'（'+(f.size/1024|0)+' KB）？更新期間請勿斷電。'))return;
const x=new XMLHttpRequest(),fd=new FormData();fd.append('fw',f,'fw.bin');otaBusy=true;
x.open('POST','/api/ota');x.setRequestHeader('Authorization','Bearer '+TOKEN);x.upload.onprogress=e=>say('上傳中 '+(e.loaded/e.total*100|0)+'%');
x.onload=()=>{let j={};try{j=JSON.parse(x.responseText)}catch(e){}otaBusy=!!j.ok;if(x.status==401){setToken('');return}
say(j.ok?'更新完成，裝置重新啟動中，約 20 秒後會自動重新連線':'更新失敗：'+(E[j.error]||j.error||x.status)+'，目前韌體未變更',!j.ok)};
x.onerror=()=>{otaBusy=false;say('連線中斷；若已傳完，裝置可能正在重新啟動，請稍後重新整理',1)};x.send(fd)}
function render(){const d=S.state?1:0;if(!d)return;$('badge').textContent=S.fw?'v'+S.fw:'';
const wn=W.saved&&!(W.sta||{}).connected?'正在連線「'+W.saved+'」':'';
$('disp').textContent=S.pos?fmt(S.display):'位置未知';$('st').textContent=(S.state=='NEEDS_TIME'&&W.saved?(wn||'已連上 Wi-Fi')+'，等待網路時間':(ST[S.state]||S.state))+(S.err?'　'+S.err:'');
$('rt').textContent=S.rtc?new Date((S.utc+S.off*60)*1000).toISOString().replace('T',' ').slice(0,19):(W.saved?'取得中…':'尚未取得（請連上 Wi-Fi）');
$('ps').textContent=S.pos?(S.mech?'已歸零':'未確認機構'):'未知';
$('sv').textContent=S.snap?(fmt(S.snapDisplay)+'（第 '+S.gen+' 次儲存'+(S.dirty?'，有未儲存變更':'')+'）'):'尚無';
$('banner').innerHTML=(S.restoring?'<p>開機自動恢復：取得網路時間後，會補跑到目前時間。</p>':'')+
(S.syncAsk?'<p>網路時間與目前時間差異超過 5 分鐘。<button onclick="act(confirmSync)">確認用網路時間校時</button></p>':'');
const idle_=!S.busy&&!busyUi;
$('bPause').disabled=S.paused&&!S.busy;$('bClear').disabled=!S.fault;
if(!filled&&S.mech){filled=true;$('q').value=(S.q/1e6).toFixed(6);$('rate').value=S.rate;$('accel').value=S.accel;$('trim').value=S.trim}
document.querySelectorAll('#app section button').forEach(b=>{if(!b.closest('#wifi')&&b.id!='bPause'&&b.id!='bClear'&&b.id!='bStop')b.disabled=!idle_});
const ready=idle_&&S.pos&&S.mech;for(const id of['bTrim','bVerify','bSave','bFinish'])$(id).disabled=!ready;
document.querySelectorAll('.tq').forEach(b=>b.disabled=!ready);
$('trimNow').textContent='目前偏移 '+S.trim+' 步'+(S.dirty?'（尚未儲存）':'（已儲存）');
let h='';if(V){h='<p>已從 <b>'+fmt(V.from)+'</b> 前進 '+V.n+' 分鐘，應該顯示 <b>'+fmt(V.to)+'</b>。</p><p>不對的話，回步驟 2 輸入實際顯示的時間，再調整偏移。</p>'}
if(h!==lastV){$('vres').innerHTML=h;lastV=h}}
function showLogin(on){$('login').hidden=!on;$('app').hidden=on;$('msg').hidden=on;if(on)$('lpw').focus()}
async function login(){const b=$('bLogin'),e=$('lerr');e.textContent='';b.disabled=true;
try{const r=await fetch('/api/login',{method:'POST',body:JSON.stringify({password:$('lpw').value})}),j=await r.json();
if(!j.ok){e.textContent=j.error=='E_LOCKED'?'嘗試太多次，請等 30 秒再試':'密碼錯誤';return}
setToken(j.token);$('lpw').value='';showLogin(false)}catch(x){e.textContent='連不到時鐘，請確認網路'}finally{b.disabled=false}}
async function changePassword(){const o=$('pold').value,n=$('pnew').value;if(n!==$('pnew2').value)throw new Error('兩次輸入的新密碼不同');
if(n.length<8||n.length>63||!/^[\x20-\x7e]+$/.test(n))throw new Error('新密碼需為 8–63 個英數字或符號');
const r=await F('/api/password',{method:'POST',body:JSON.stringify({old:o,new:n})}),j=await r.json();
if(!j.ok)throw new Error(j.error=='E_WRONG'?'目前密碼不正確':j.error=='E_PASSWORD'?'新密碼格式不正確':'儲存失敗，密碼未變更');
setToken(j.token);for(const i of['pold','pnew','pnew2'])$(i).value='';
say('密碼已更改。熱點密碼也一起改了，用熱點連線的裝置要用新密碼重連；其他瀏覽器需重新登入')}
if(TOKEN)showLogin(false);else showLogin(true);
(async()=>{for(let n=0;;++n){if(!TOKEN){await new Promise(r=>setTimeout(r,500));continue}
try{await refresh();if(/^(連線中…|與時鐘連線中斷)/.test($('msg').textContent))say('已連線');if(!wifiBusy&&n%4==0)await wifiRefresh()}catch(e){if(TOKEN&&!otaBusy&&!wifiBusy)say('與時鐘連線中斷，重試中…',1)}await new Promise(r=>setTimeout(r,1000))}})();
</script></body></html>)HTML";
