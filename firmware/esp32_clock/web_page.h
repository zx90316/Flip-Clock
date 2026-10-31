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
</style></head><body><main>
<h1>翻頁時鐘 <small id="badge"></small></h1>
<section><div class="big" id="disp">--:--</div>
<dl><dt>狀態</dt><dd id="st"></dd><dt>Uno 連線</dt><dd id="lk"></dd><dt>RTC 時間</dt><dd id="rt"></dd>
<dt>位置記憶</dt><dd id="ps"></dd><dt>已儲存</dt><dd id="sv"></dd></dl>
<div id="banner"></div>
<div class="row"><button id="bPause" onclick="act(pause)">暫停走時</button>
<button class="d" onclick="stopNow()">緊急停止</button><button id="bClear" onclick="act(clearFault)">清除故障</button></div></section>

<section><h2>1. 校時</h2><p>用這支手機的時間寫入 RTC，並採用手機的時區。</p>
<div class="row"><button class="p" id="bTime" onclick="act(timeSync)">用手機時間校時</button></div></section>

<section><h2>2. 手動歸零</h2>
<p>只能正向轉動。按下面的按鈕讓機構轉到「某個你看得出的時間」，再輸入實際顯示的時間。</p>
<div class="row"><button onclick="act(()=>jog(1))">+1 步</button><button onclick="act(()=>jog(8))">+8 步</button>
<button onclick="act(()=>jog(32))">+32 步</button><button onclick="act(()=>jog(136))">+136 步</button></div>
<div class="row">實際顯示 <input id="ah" type="number" min="1" max="12" value="12"> : <input id="am" type="number" min="0" max="59" value="0">
每頁步數 <input id="q" type="number" step="0.001" value="136"></div>
<div class="row"><button class="p" id="bAlign" onclick="act(align)">記住為歸零位置</button></div></section>

<section><h2>3. 試跑確認</h2><p>機構會連續換頁到差異較大的時間，請在每一步核對實際顯示。全部換頁需數分鐘。</p>
<div id="tests"></div></section>

<section><h2>4. 完成歸零</h2><p>儲存位置並啟動自動走時。之後斷電重啟，會依記憶位置自動補跑到目前時間。</p>
<div class="row"><button class="p" id="bFinish" onclick="act(finish)">完成歸零並啟動自動走時</button></div></section>
<section><h2>韌體更新（OTA）</h2><p>選擇 <b>esp32_clock.ino.bin</b>。更新前會自動暫停走時；更新完成後裝置重新啟動，位置與設定都保留。更新期間請勿斷電。</p>
<div class="row"><input type="file" id="fw" accept=".bin" style="width:auto"><button class="d" onclick="ota()">上傳並更新</button></div></section>
</main><div id="msg" class="ok">連線中…</div>
<script>
const $=i=>document.getElementById(i),pad=n=>String(n).padStart(2,'0');
const E={E_BUSY:'裝置忙碌，請先按「暫停走時」並等動作結束',E_TIME_INVALID:'RTC 時間無效，請先校時',E_I2C:'I²C 失敗：可能是 Uno 連線異常，或校時時讀寫不到 RTC，請檢查接線與 RTC 模組',
E_NOT_CALIBRATED:'尚未歸零，請先完成步驟 2',E_RANGE:'數值超出範圍',E_FAULT:'系統故障，請先按「清除故障」',E_PLAN_STALE:'預覽已過期，請重試',
E_REVERSE_DISABLED:'目前只支援正向轉動',E_SAVE_THROTTLED:'5 秒內不能重複儲存，請稍後再試',E_NVS:'儲存失敗',
E_OTA_NO_PARTITION:'此韌體的分割表沒有 OTA 分區，需先用 UART 燒錄一次',E_OTA_IMAGE:'不是有效的 ESP32 韌體檔',E_OTA_WRITE:'寫入 Flash 失敗',
E_OTA_END:'映像驗證失敗',E_AUTH:'未授權'};
const ST={IDLE:'待命（自動走時中）',PAUSED:'已暫停',MOVING:'換頁中',LINK_WAIT:'等待 Uno 連線',NEEDS_TIME:'需要校時',NEEDS_CALIBRATION:'需要歸零',
NEEDS_CATCHUP_CONFIRM:'需要確認補跑',FAULT:'故障'};
let S={},busyUi=false,T={tests:[],i:0};
const OFFS=[67,181,241];
const fmt=(i,c)=>{c=c||S.cycle||720;const h=Math.floor(i/60);return(c==720?(h%12||12):pad(h))+':'+pad(i%60)};
const say=(t,bad)=>{const e=$('msg');e.textContent=t;e.className=bad?'bad':'ok'};
async function api(op,a){const r=await fetch('/api/cmd',{method:'POST',body:JSON.stringify(Object.assign({op},a||{}))});
let j={phase:'error',code:'E_EMPTY'};for(const l of (await r.text()).trim().split('\n')){try{j=JSON.parse(l)}catch(e){}}return j}
async function run(op,a){const j=await api(op,a);if(j.phase=='error')throw new Error((E[j.code]||'失敗')+'（'+j.code+'）');return j}
async function refresh(){S=await(await fetch('/api/state')).json();render()}
async function idle(ms){const t=Date.now();for(;;){await new Promise(r=>setTimeout(r,500));await refresh();if(!S.busy)return;if(Date.now()-t>ms)throw new Error('等待逾時')}}
async function act(fn){if(busyUi)return;busyUi=true;render();try{await fn()}catch(e){say(e.message,1)}busyUi=false;try{await refresh()}catch(e){}}
async function pause(){await run('pause');await idle(30000);say('已暫停')}
async function stopNow(){try{await run('stop');say('已停止馬達，位置需重新確認',1)}catch(e){say(e.message,1)}}
async function clearFault(){await run('clear_fault');await idle(15000);say('已清除故障，請重新確認顯示位置')}
async function timeSync(){const off=-new Date().getTimezoneOffset();await run('set_config',{values:{utc_offset_min:off}});
await run('set_time',{utc_s:Math.floor(Date.now()/1000)});say('已用手機時間校時（UTC'+(off>=0?'+':'')+off/60+'）')}
async function jog(n){await run('jog_steps',{steps:n});await idle(60000);say('已轉動 '+n+' 步，位置需重新輸入')}
async function align(){const h=+$('ah').value,m=+$('am').value,q=Math.round(parseFloat($('q').value)*1e6);
if(!(h>=1&&h<=12&&m>=0&&m<=59&&q>0))throw new Error('時間或每頁步數不正確');
await run('set_config',{values:{mechanics_confirmed:true,cycle_minutes:720,steps_per_page_u6:q,max_step_rate:200,acceleration:800}});
await run('set_display',{hour:h%12,minute:m,aligned:true});T={tests:OFFS.map(o=>({off:o,st:'todo'})),i:0};say('已記住 '+h+':'+pad(m)+' 為目前位置')}
async function forward(pages,label){let left=pages,done=0;const base=S.display;
while(left>0){const n=Math.min(60,left);await run('advance_pages',{pages:n});await idle(240000);left-=n;done+=n;
if(!S.pos||S.display!=(base+done)%S.cycle)throw new Error('換頁中斷，位置未知，請重新歸零');say(label+'：已換 '+done+' / '+pages+' 頁')}}
async function goTest(){await refresh();const t=T.tests[T.i];t.start=S.display;t.target=(S.display+t.off)%S.cycle;
await forward(t.off,'測試 '+(T.i+1));t.st='ask'}
function passTest(){T.tests[T.i].st='pass';T.i++;say('此組符合')}
function failTest(){T.tests[T.i].st='fail'}
async function fixTest(){const t=T.tests[T.i],h=+$('oh').value,m=+$('om').value,obs=(h%12)*60+m,P=t.off;
const O=(obs-t.start+S.cycle)%S.cycle,q=S.q/1e6;let qn=null;if(O>0&&P/O>0.5&&P/O<2)qn=q*P/O;
if(qn&&Math.abs(qn-q)>0.05&&!confirm('依實際移動 '+O+' 頁（預期 '+P+' 頁），建議每頁步數 '+q.toFixed(3)+' → '+qn.toFixed(3)+'。要套用嗎？'))qn=null;
if(qn&&Math.abs(qn-q)>0.05){await run('set_config',{values:{steps_per_page_u6:Math.round(qn*1e6)}});$('q').value=qn.toFixed(3)}
await run('set_display',{hour:h%12,minute:m,aligned:true});T.tests=OFFS.map(o=>({off:o,st:'todo'}));T.i=0;
say('已用實際顯示重新對齊'+(qn?'並修正每頁步數':'')+'，請從試跑 1 重新確認',1)}
async function finish(){await run('set_config',{values:{mechanics_confirmed:true}});await run('save_config');await idle(30000);
if(S.dirty)throw new Error('儲存失敗，請稍候 5 秒再試');const p=await run('preview_sync');await run('resume',{plan_id:p.plan_id,confirm_large:true});
say('歸零完成並已儲存，正在補跑到目前時間，之後自動走時')}
let otaBusy=false;
function ota(){const f=$('fw').files[0];if(!f)return say('請先選擇 .bin 檔',1);
if(!confirm('更新韌體 '+f.name+'（'+(f.size/1024|0)+' KB）？更新期間請勿斷電。'))return;
const x=new XMLHttpRequest(),fd=new FormData();fd.append('fw',f,'fw.bin');otaBusy=true;
x.open('POST','/api/ota');x.upload.onprogress=e=>say('上傳中 '+(e.loaded/e.total*100|0)+'%');
x.onload=()=>{let j={};try{j=JSON.parse(x.responseText)}catch(e){}otaBusy=!!j.ok;
say(j.ok?'更新完成，裝置重新啟動中，約 20 秒後會自動重新連線':'更新失敗：'+(E[j.error]||j.error||x.status)+'，目前韌體未變更',!j.ok)};
x.onerror=()=>{otaBusy=false;say('連線中斷；若已傳完，裝置可能正在重新啟動，請稍後重新整理',1)};x.send(fd)}
function render(){const d=S.state?1:0;if(!d)return;$('badge').textContent=S.fw?'v'+S.fw:'';
$('disp').textContent=S.pos?fmt(S.display):'位置未知';$('st').textContent=(ST[S.state]||S.state)+(S.err?'　'+S.err:'');
$('lk').textContent=S.link?'已連線':'未連線';
$('rt').textContent=S.rtc?new Date((S.utc+S.off*60)*1000).toISOString().replace('T',' ').slice(0,19):'無效，請先校時';
$('ps').textContent=S.pos?(S.mech?'已歸零':'未確認機構'):'未知';
$('sv').textContent=S.snap?(fmt(S.snapDisplay)+'（第 '+S.gen+' 次儲存'+(S.dirty?'，有未儲存變更':'')+'）'):'尚無';
$('banner').innerHTML=S.restoring?'<p>開機自動恢復：等待時間與 Uno 就緒後，會補跑到目前時間。</p>':'';
const idle_=S.paused&&!S.busy&&!busyUi;
$('bPause').disabled=S.paused&&!S.busy;$('bClear').disabled=!S.fault;
for(const id of['bTime','bAlign','bFinish'])$(id).disabled=!idle_;
document.querySelectorAll('section button').forEach(b=>{if(!b.id&&!b.closest('#tests'))b.disabled=!idle_});
$('bFinish').disabled=!idle_||!S.pos||!S.mech||T.i<T.tests.length||!T.tests.length&&!S.snap;
let h='';T.tests.forEach((t,i)=>{const lab='測試 '+(i+1)+'：再前進 '+Math.floor(t.off/60)+' 小時 '+t.off%60+' 分';
if(t.st=='pass')h+='<div class="t pass">'+lab+' ✓</div>';
else if(i==T.i){h+='<div class="t"><b>'+lab+'</b>';
if(t.st=='todo')h+='<div class="row"><button class="p" '+(idle_&&S.pos?'':'disabled')+' onclick="act(goTest)">開始前進</button></div>';
if(t.st=='ask')h+='<p>預期顯示 <b>'+fmt(t.target)+'</b>，實際是嗎？</p><div class="row"><button class="p" onclick="passTest();render()">符合</button><button onclick="failTest();render()">不符</button></div>';
if(t.st=='fail')h+='<p>輸入實際顯示的時間：</p><div class="row"><input id="oh" type="number" min="1" max="12" value="12"> : <input id="om" type="number" min="0" max="59" value="0"><button class="p" onclick="act(fixTest)">修正並重來</button></div>';
h+='</div>'}else h+='<div class="t">'+lab+'</div>'});
h=h||'<p>先完成步驟 2。</p>';if(h!==T.h){$('tests').innerHTML=h;T.h=h}}
(async()=>{for(;;){try{await refresh()}catch(e){if(!otaBusy)say('與時鐘連線中斷，重試中…',1)}await new Promise(r=>setTimeout(r,1000))}})();
</script></body></html>)HTML";
