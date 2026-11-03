// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <Arduino.h>
// Single-page commissioning UI. All behaviour is decided by the firmware; this page only issues
// the same protocol operations as BLE and polls /api/state.
static const char WEB_PAGE[] PROGMEM = R"HTML(<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>翻頁時鐘</title>
<style>
:root{--bg:#f4f6fb;--card:#fff;--ink:#172039;--mut:#66738b;--line:#e5e9f2;--blue:#4157d8;--blue-deep:#3346b7;--blue-soft:#edf0ff;--green:#16805d;--green-soft:#e8f7f0;--red:#ba3f4b;--red-soft:#fff0f1;--shadow:0 14px 36px rgba(31,48,95,.055)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Microsoft JhengHei",sans-serif}button,input{font:inherit}button{min-height:42px;padding:9px 15px;border:1px solid #cfd6e4;border-radius:10px;background:#fff;color:#253456;font-weight:650;cursor:pointer;transition:background .18s,border-color .18s,transform .18s}button:hover:not(:disabled){background:#f4f6ff;border-color:#aab5d3;transform:translateY(-1px)}button:disabled{opacity:.45;cursor:not-allowed}button.p{background:var(--blue);border-color:var(--blue);color:#fff;box-shadow:0 5px 14px rgba(65,87,216,.18)}button.p:hover:not(:disabled){background:var(--blue-deep);border-color:var(--blue-deep)}button.d{color:var(--red);border-color:#efc8cf;background:#fff}button.d:hover:not(:disabled){background:var(--red-soft);border-color:var(--red)}a{color:inherit}a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #a9b8ff;outline-offset:2px}input{min-height:42px;width:100%;padding:9px 12px;border:1px solid #cfd6e4;border-radius:10px;background:#fff;color:var(--ink);outline:none}input:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(65,87,216,.12)}input[type=file]{padding:9px;width:100%;max-width:420px}input[type=file]::file-selector-button{border:0;border-radius:7px;background:var(--blue-soft);color:var(--blue-deep);padding:7px 10px;margin-right:12px;font:inherit;font-weight:650;cursor:pointer}input.w{width:100%}input.m{width:165px}p{margin:8px 0;color:var(--mut)}h1,h2,h3{line-height:1.25;letter-spacing:-.025em}h2{font-size:21px;margin:0 0 8px}h3{font-size:16px;margin:20px 0 10px}small{font-size:13px}dl,dd{margin:0}code{padding:2px 5px;border-radius:5px;background:#f0f2f8;font-size:.9em}
.shell{min-height:100vh;display:grid;grid-template-columns:242px minmax(0,1fr)}.sidebar{position:sticky;top:0;height:100vh;padding:28px 17px 20px;background:#151d34;color:#dbe3f8;display:flex;flex-direction:column;z-index:2}.brand{display:flex;align-items:center;gap:11px;padding:2px 10px 32px;color:#fff;text-decoration:none;font-size:18px;font-weight:800;letter-spacing:-.035em}.brand-mark{display:flex;gap:3px;align-items:center}.brand-mark i{position:relative;width:20px;height:27px;border-radius:4px;background:#e7ebff;color:#233167;display:grid;place-items:center;font-size:14px;font-style:normal;font-weight:900;line-height:1}.brand-mark i:after{content:"";position:absolute;left:0;right:0;top:50%;height:1px;background:#a7b4db}.side-label{padding:0 13px 9px;color:#8793b1;font-size:11px;letter-spacing:.17em;font-weight:800}.nav{display:grid;gap:4px}.nav a{display:flex;align-items:center;gap:11px;padding:11px 13px;border-radius:9px;color:#b9c4dd;text-decoration:none;font-weight:650}.nav a:hover,.nav a:focus-visible{background:#273355;color:#fff}.nav-n{width:21px;text-align:center;color:#899bd9;font-size:12px;font-variant-numeric:tabular-nums}.side-foot{margin-top:auto;padding:16px 13px 0;border-top:1px solid #33405e;color:#8793b1;font-size:12px;line-height:1.7}.side-foot b{display:block;color:#dbe3f8;font-size:13px}
.content{min-width:0;width:min(100%,1250px);margin:0 auto;padding:30px clamp(18px,3.3vw,48px) 84px}.topbar{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:25px}.eyebrow{margin:0 0 7px;color:var(--blue);font-size:11px;letter-spacing:.17em;font-weight:850;text-transform:uppercase}.topbar h1{font-size:31px;margin:0}.topbar p{margin:6px 0 0}.version{flex:none;display:inline-flex;align-items:center;padding:7px 11px;border:1px solid #d9def0;border-radius:999px;background:#fff;color:#58658b;font-size:12px;font-weight:750}.stack{display:grid;grid-template-columns:minmax(0,1fr);gap:20px}section,.grid-two,.security-grid{scroll-margin-top:24px}.panel{min-width:0;padding:25px 27px;background:var(--card);border:1px solid var(--line);border-radius:17px;box-shadow:var(--shadow)}.panel-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:16px}.panel-head p{margin:4px 0 0}.step{display:inline-flex;align-items:center;justify-content:center;min-width:31px;height:31px;border-radius:9px;background:var(--blue-soft);color:var(--blue-deep);font-size:12px;font-weight:850}.optional{display:inline-block;padding:4px 9px;border-radius:99px;background:#f1f3f8;color:#586681;font-size:11px;font-weight:750}.hint{font-size:13px}.row{display:flex;flex-wrap:wrap;align-items:center;gap:9px;margin:12px 0}.row:last-child{margin-bottom:0}.row button{flex:none}.grid-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.field{display:grid;gap:6px;min-width:0}.field label,.field-label{font-size:12px;font-weight:750;color:#4d5c76}.field.full{grid-column:1/-1}.compact-input{max-width:120px}.time-inputs{display:flex;align-items:center;gap:8px}.time-inputs input{width:85px;text-align:center;font-size:18px;font-weight:750;font-variant-numeric:tabular-nums}.time-inputs span{color:var(--mut);font-weight:800}.form-action{margin-top:16px}.form-action .p{min-width:145px}.divider{height:1px;background:var(--line);margin:20px 0}.subtle{color:var(--mut);font-size:13px}.inline-note{padding:12px 14px;border:1px solid #d9e1f3;border-radius:10px;background:#f7f9ff;color:#465778;font-size:13px}.inline-note p{margin:0}
.overview{padding:0;overflow:hidden;border:0;background:#1b2747;color:#fff;box-shadow:0 18px 32px rgba(25,40,82,.14)}.overview-top{padding:28px 30px 27px;background:radial-gradient(circle at 90% 0,rgba(115,135,255,.35),transparent 42%),linear-gradient(115deg,#1a284f,#263b6b)}.overview .eyebrow{color:#a7b9ff}.overview-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.overview h2{font-size:16px;font-weight:650;color:#cbd5f2;margin:0}.big{font-size:clamp(58px,7vw,94px);line-height:1.05;font-weight:760;letter-spacing:-.065em;font-variant-numeric:tabular-nums;margin:10px 0 7px;color:#fff}.state-line{display:flex;align-items:center;gap:8px;color:#e1e8ff;font-size:14px}.state-dot{width:8px;height:8px;flex:none;border-radius:99px;background:#f6c76f;box-shadow:0 0 0 4px rgba(246,199,111,.14)}.state-dot.good{background:#72dfb3;box-shadow:0 0 0 4px rgba(114,223,179,.15)}.state-dot.bad{background:#ff8494;box-shadow:0 0 0 4px rgba(255,132,148,.15)}.overview-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:23px}.overview-actions button{background:#fff;color:#213057;border-color:#fff}.overview-actions button:hover:not(:disabled){background:#eaf0ff}.overview-actions button.d{background:transparent;color:#ffb1ba;border-color:#a86070}.overview-actions button.d:hover:not(:disabled){background:rgba(255,255,255,.08)}.telemetry{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;background:#fff;color:var(--ink)}.telemetry>div{padding:18px 24px;border-right:1px solid var(--line)}.telemetry>div:last-child{border:0}.telemetry dt,.metric dt{font-size:11px;font-weight:800;letter-spacing:.09em;color:#8793a9;text-transform:uppercase}.telemetry dd{margin-top:6px;font-size:14px;font-weight:700;overflow-wrap:anywhere}.overview #banner{padding:0 24px;background:#fff;color:var(--ink)}.overview #banner:not(:empty){padding:14px 24px;border-top:1px solid var(--line)}#banner p{color:#465878;margin:0 0 8px}#banner p:last-child{margin-bottom:0}
.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:18px 0}.metric{min-width:0;padding:15px;border:1px solid var(--line);border-radius:12px;background:#fafbfe}.metric dt{margin-bottom:7px}.metric dd{font-size:15px;font-weight:750;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}.plan-layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(240px,.65fr);gap:20px;margin-top:16px}.plan-block{min-width:0}.plan-block h3{margin-top:0}.plan-caption{font-size:12px}.plan{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums;min-width:420px}.plan th,.plan td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:right}.plan th{background:#f7f8fc;color:#69768c;font-size:11px;font-weight:800}.plan th:first-child,.plan td:first-child{text-align:left}.plan td:first-child{font-weight:700}.plan tr:last-child td{border-bottom:0}#planActive,#planDraft{max-width:100%;overflow-x:auto}#planActive>p,#planDraft>p{font-weight:700;color:#344461;margin-top:12px}.draft-box{min-width:0;padding:18px;border:1px solid #dfe3f7;border-radius:13px;background:#f8f9ff}.draft-box h3{margin:0 0 10px}.draft-box .row{margin:0 0 10px}.draft-box input{flex:1;min-width:125px}.draft-box button{font-size:12px;padding:8px 10px}.draft-box #planDraft{margin-top:16px}.draft-box #planDraft .plan{min-width:420px}
.save-panel{background:#f0f3ff;border-color:#dce3ff}.save-panel h2{color:#263b95}.save-panel .p{min-width:210px}.save-panel .hint{margin-top:12px}.input-unit{white-space:nowrap;color:var(--mut);font-size:13px}.trim-value{display:inline-block;margin:2px 0 10px;padding:7px 10px;border-radius:8px;background:#f3f5fa;color:#44516a;font-size:12px;font-weight:700}.tq{min-width:49px}.verify-result:not(:empty){padding:12px 14px;border:1px solid #d8e5fc;border-radius:10px;background:#f5f8ff;margin-top:12px}.verify-result p{margin:0 0 5px}.verify-result p:last-child{margin:0}details{border-top:1px solid var(--line);margin-top:20px;padding-top:14px}summary{cursor:pointer;color:#475fc5;font-weight:750;list-style:none}summary:before{content:"+";display:inline-grid;place-items:center;width:20px;height:20px;border-radius:5px;background:var(--blue-soft);margin-right:8px}details[open] summary:before{content:"−"}
.connection-status{padding:15px;border:1px solid #d8e9e0;background:#f6fbf8;border-radius:12px}.connection-status .label{display:block;font-size:11px;font-weight:850;letter-spacing:.11em;color:var(--green);margin-bottom:4px}.connection-status #wst{font-weight:700;overflow-wrap:anywhere}.connection-status.setup{background:#fff9ed;border-color:#f1deb6}.connection-status.setup .label{color:#9b6815}.connection-status.trial{background:#f5f7ff;border-color:#dce2fb}.connection-status.trial .label{color:var(--blue-deep)}.wifi-form{margin-top:18px}.network-list{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 14px}.network-list button{font-size:13px}#wlan:not([hidden]){margin-top:13px;padding:14px;border:1px solid #bfe8d2;border-radius:12px;background:var(--green-soft)}#wlan a{color:#1e6093;font-weight:750}#wlan button{margin-top:5px}.security-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.security-grid .panel{height:100%}
#msg{position:fixed;right:22px;bottom:18px;max-width:min(540px,calc(100vw - 36px));z-index:10;padding:12px 16px 12px 37px;border:1px solid #b9dfce;border-radius:12px;background:#f0fff7;color:#146448;box-shadow:0 14px 30px rgba(22,41,73,.17);font-size:13px;font-weight:650}#msg:before{content:"";position:absolute;left:16px;top:19px;width:9px;height:9px;border-radius:99px;background:#2bb57e}#msg.bad{background:#fff3f4;color:#a53242;border-color:#f1c1c8}#msg.bad:before{background:#dc5a6b}.err{color:var(--red);min-height:1.5em;font-size:13px}[hidden]{display:none!important}
.auth-layout{min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 75% 10%,#e4eaff,transparent 42%),var(--bg)}.auth-inner{width:min(100%,420px)}.auth-brand{display:flex;align-items:center;gap:12px;justify-content:center;margin-bottom:28px;font-size:24px;font-weight:850}.auth-brand .brand-mark i{width:25px;height:34px;font-size:18px;background:var(--blue);color:#fff}.auth-card{padding:32px;border:1px solid var(--line);border-radius:18px;background:#fff;box-shadow:0 20px 60px rgba(27,43,87,.09)}.auth-card h1{font-size:25px;margin:0 0 6px}.auth-card p{font-size:14px}.auth-card form{margin-top:24px}.auth-card button{width:100%}.auth-foot{text-align:center;font-size:12px;color:var(--mut);margin-top:18px}
@media(max-width:1050px){.shell{grid-template-columns:205px minmax(0,1fr)}.plan-layout{grid-template-columns:minmax(0,1fr)}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.security-grid{grid-template-columns:minmax(0,1fr)}}
@media(max-width:720px){.shell{display:block}.sidebar{height:auto;padding:12px 14px 10px;position:sticky;top:0;box-shadow:0 6px 18px rgba(16,26,50,.13)}.brand{padding:0 4px 10px;font-size:15px}.brand-mark i{width:15px;height:21px;font-size:11px}.side-label,.side-foot{display:none}.nav{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none}.nav::-webkit-scrollbar{display:none}.nav a{white-space:nowrap;padding:7px 10px;font-size:12px}.nav-n{display:none}.content{padding:23px 15px 90px}.topbar{margin-bottom:18px}.topbar h1{font-size:25px}.topbar p{font-size:12px}.stack{gap:14px}section,.grid-two,.security-grid{scroll-margin-top:108px}.panel{padding:20px 18px;border-radius:14px}.overview-top{padding:23px 21px}.big{font-size:clamp(60px,17vw,82px)}.telemetry>div{padding:13px 11px}.telemetry dt{font-size:10px}.telemetry dd{font-size:12px}.grid-two,.security-grid{grid-template-columns:minmax(0,1fr);gap:14px}.metric-grid{gap:8px}.metric{padding:12px}.metric dd{font-size:13px}.row button{max-width:100%}#msg{left:12px;right:12px;bottom:11px;max-width:none}.plan{min-width:390px;font-size:12px}}
@media(max-width:420px){.telemetry{grid-template-columns:1fr}.telemetry>div{border-right:0;border-bottom:1px solid var(--line);padding:10px 16px}.telemetry>div:last-child{border-bottom:0}.form-grid{grid-template-columns:1fr}.topbar h1{font-size:22px}.version{font-size:10px;padding:6px 8px}.overview-actions button{flex:1}.save-panel .p{width:100%}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}button{transition:none}}
</style></head><body>
<main id="login" class="auth-layout" hidden><div class="auth-inner">
<div class="auth-brand"><span class="brand-mark" aria-hidden="true"><i>1</i><i>2</i></span> FLIP CLOCK</div>
<section class="auth-card"><p class="eyebrow">DEVICE CONSOLE</p><h1>登入裝置</h1><p>輸入時鐘熱點的 Wi-Fi 密碼，開啟本機控制台。此瀏覽器會記住登入狀態。</p>
<form onsubmit="login();return false"><div class="field"><label for="lpw">裝置密碼</label><input id="lpw" class="w" type="password" placeholder="輸入密碼" autocomplete="current-password" required></div>
<div class="row form-action"><button class="p" id="bLogin">登入控制台</button></div><p class="err" id="lerr" role="alert"></p></form></section>
<p class="auth-foot">本機裝置管理 · 請連線至 FlipClock 熱點或相同 Wi-Fi</p></div></main>
<main id="app" class="shell" hidden>
<aside class="sidebar"><a class="brand" href="#overview"><span class="brand-mark" aria-hidden="true"><i>1</i><i>2</i></span><span>FLIP CLOCK</span></a>
<div class="side-label">裝置管理</div><nav class="nav" aria-label="設定導覽">
<a href="#overview"><span class="nav-n">01</span>總覽</a><a href="#motion"><span class="nav-n">02</span>步數規劃</a>
<a href="#setup"><span class="nav-n">03</span>校時與歸零</a><a href="#wifi"><span class="nav-n">04</span>Wi-Fi 網路</a>
<a href="#account"><span class="nav-n">05</span>安全設定</a><a href="#firmware"><span class="nav-n">06</span>韌體更新</a></nav>
<div class="side-foot"><b>本機控制台</b>設定直接作用於這台翻頁時鐘。</div></aside>
<div class="content"><header class="topbar"><div><p class="eyebrow">DEVICE CONSOLE / SETTINGS</p><h1>時鐘控制台</h1><p>監看走時、調整機構與管理網路連線</p></div><span class="version" id="badge"></span></header>
<div class="stack">
<section id="overview" class="panel overview" aria-label="裝置總覽"><div class="overview-top"><div class="overview-head"><div><p class="eyebrow">LIVE DISPLAY</p><h2>目前顯示</h2></div></div>
<div class="big" id="disp">--:--</div><div class="state-line"><span id="stateDot" class="state-dot" aria-hidden="true"></span><span id="st">讀取裝置狀態中</span></div>
<div class="overview-actions"><button id="bPause" onclick="act(pause)">暫停走時</button><button class="d" id="bStop" onclick="stopNow()">緊急停止</button><button id="bClear" onclick="act(clearFault)">清除故障</button></div></div>
<dl class="telemetry"><div><dt>裝置時間</dt><dd id="rt">--</dd></div><div><dt>位置狀態</dt><dd id="ps">--</dd></div><div><dt>儲存快照</dt><dd id="sv">--</dd></div></dl><div id="banner"></div></section>

<section id="motion" class="panel"><div class="panel-head"><div><p class="eyebrow">MOTION PLANNING</p><h2>每分鐘步數與餘數</h2><p>設定值、馬達進度與後續換頁規劃</p></div><span class="step">01</span></div>
<dl class="metric-grid"><div class="metric"><dt>目前生效</dt><dd id="qActive">--</dd></div><div class="metric"><dt>已儲存</dt><dd id="qSaved">--</dd></div>
<div class="metric"><dt>累積餘數</dt><dd id="remNow">--</dd></div><div class="metric"><dt>移動剩餘</dt><dd id="leftNow">--</dd></div></dl>
<p class="hint">馬達每次只走整數個半步；不足 1 步的餘數會累積到後續換頁。表格依顯示位置往前規劃；連續補跑時可能合併移動。</p>
<div class="plan-layout"><div class="plan-block"><h3>目前設定 · 接下來 10 次換頁</h3><div id="planActive"></div></div>
<div class="draft-box"><h3>調整每分鐘步數</h3><div class="field"><label for="q">步數草稿（半步／分鐘）</label><div class="row"><input id="q" class="m" type="number" min="1" max="10000" step="0.000001" value="136.533333" oninput="qDraftChanged()"><button id="bResetQ" onclick="resetQDraft()">恢復目前設定</button></div></div>
<p class="hint">輸入只更新試算。要套用請到下方按「以此歸零」；前進驗證是選做。</p><div id="planDraft" hidden></div></div></div></section>

<div id="setup" class="grid-two"><section class="panel"><div class="panel-head"><div><p class="eyebrow">TIME SOURCE</p><h2>校時</h2><p>連上 Wi-Fi 後自動從網路校時</p></div><span class="step">02</span></div>
<p>時鐘沒有電池 RTC。沒有網路時，可暫時使用手機時間；斷電後需重新校時。</p><div class="row"><button id="bTime" onclick="act(timeSync)">暫時用手機時間</button><button onclick="act(tzSync)">套用手機時區</button></div></section>
<section class="panel"><div class="panel-head"><div><p class="eyebrow">ALIGN DISPLAY</p><h2>歸零與套用步數</h2><p>將裝置位置對齊時鐘實際顯示</p></div><span class="step">03</span></div>
<div class="field"><label for="ah">時鐘現在顯示</label><div class="time-inputs"><input id="ah" type="number" min="1" max="12" value="12" aria-label="小時"><span>:</span><input id="am" type="number" min="0" max="59" value="0" aria-label="分鐘"></div></div>
<p class="hint">歸零時馬達不轉動，同時套用上方的步數草稿。</p><div class="row form-action"><button class="p" id="bZero" onclick="act(zero)">以此歸零</button></div>
<details><summary>進階：速度與加速度</summary><div class="form-grid" style="margin-top:14px"><div class="field"><label for="rate">最高速度（步／秒）</label><input id="rate" type="number" min="10" max="1000" value="900"></div><div class="field"><label for="accel">加速度（步／秒²）</label><input id="accel" type="number" min="1" max="4000" value="400"></div></div>
<p class="hint">馬達只嗡嗡響或漏步時請調低。修改後按「以此歸零」套用。</p></details></section></div>

<section id="save" class="panel save-panel"><div class="panel-head"><div><p class="eyebrow">SAVE & START</p><h2>儲存並開始走時</h2><p>歸零後即可直接儲存；前進驗證不是必要步驟。</p></div><span class="step">04</span></div>
<div class="row"><button class="p" id="bFinish" onclick="act(finish)">儲存並開始走時</button><button id="bSave" onclick="act(saveOnly)">只儲存設定</button></div><p class="hint">設定與位置會保留在裝置中，重新開機後可依儲存位置恢復。</p></section>

<div class="grid-two"><section class="panel"><div class="panel-head"><div><p class="eyebrow">MANUAL ADVANCE</p><h2>手動進步</h2><p>調整分輪角度，協助翻片越過卡住的位置</p></div><span class="optional">選用</span></div>
<p class="hint">只讓馬達向前走指定的整數半步，不改顯示位置、餘步或已儲存設定。若實際顯示因此換頁，請重新歸零。</p>
<div class="row"><button class="manual-step" onclick="act(()=>manualAdvance(1))">+1</button><button class="manual-step" onclick="act(()=>manualAdvance(4))">+4</button><button class="manual-step" onclick="act(()=>manualAdvance(8))">+8</button><button class="manual-step" onclick="act(()=>manualAdvance(32))">+32</button></div>
<div class="row"><input id="manualSteps" class="compact-input" type="number" min="1" max="8000" step="1" value="8" aria-label="手動前進半步數"><span class="input-unit">半步</span><button id="bManualSteps" onclick="act(()=>manualAdvance(+$('manualSteps').value))">向前走</button></div></section>
<section class="panel"><div class="panel-head"><div><p class="eyebrow">CHECK MOVEMENT</p><h2>前進檢查</h2><p>觀察實際翻頁結果</p></div><span class="optional">選用</span></div>
<p>可前進任意分鐘數，再對照實際顯示。略過此步也能儲存並開始走時。</p><div class="row"><input id="vm" class="compact-input" type="number" min="1" max="720" value="10" aria-label="前進分鐘數"><span class="input-unit">分鐘</span><button id="bVerify" onclick="act(()=>verify(+$('vm').value))">前進</button></div>
<div class="row"><button class="tq" onclick="act(()=>verify(1))">1 分鐘</button><button class="tq" onclick="act(()=>verify(60))">1 小時</button></div><div id="vres" class="verify-result" aria-live="polite"></div>
<p class="hint">前進後若顯示比現在快，時鐘會等時間追上；也可選擇轉一圈對時。</p></section></div>
<section id="wifi" class="panel"><div class="panel-head"><div><p class="eyebrow">CONNECTIVITY</p><h2>Wi-Fi 網路</h2><p>連上 2.4 GHz 網路以取得時間，並從區網開啟控制台</p></div><span class="step">05</span></div>
<div id="wifiStatus" class="connection-status"><span class="label">目前連線</span><div id="wst">--</div></div><div id="wlan" hidden></div>
<div class="wifi-form"><div class="row"><button id="bScan" onclick="wifiScan()">掃描附近網路</button><button id="bRetrySaved" onclick="wifiRetrySaved()">重試已儲存 Wi-Fi</button></div>
<p class="hint">掃描或試連時，裝置熱點可能短暫中斷；完成後頁面會重新連線。找不到網路時可手動輸入名稱。</p><div id="wnets" class="network-list"></div>
<div class="form-grid"><div class="field"><label for="wss">Wi-Fi 名稱</label><input id="wss" placeholder="輸入或從上方選擇" autocomplete="off"></div><div class="field"><label for="wpw">Wi-Fi 密碼</label><input id="wpw" type="password" placeholder="開放網路請留空" autocomplete="off"></div></div>
<div class="row form-action"><button class="p" id="bConn" onclick="wifiConnect()">測試連線並儲存</button><button id="bForget" class="d" onclick="wifiForget()">忘記已儲存的網路</button></div></div></section>

<div class="security-grid"><section id="account" class="panel"><div class="panel-head"><div><p class="eyebrow">ACCESS CONTROL</p><h2>安全設定</h2><p>變更網頁與裝置熱點共用的密碼</p></div><span class="step">06</span></div>
<div class="form-grid"><div class="field full"><label for="pold">目前密碼</label><input id="pold" class="w" type="password" autocomplete="current-password"></div><div class="field"><label for="pnew">新密碼</label><input id="pnew" class="w" type="password" autocomplete="new-password"></div><div class="field"><label for="pnew2">確認新密碼</label><input id="pnew2" class="w" type="password" autocomplete="new-password"></div></div>
<p class="hint">新密碼需為 8–63 個英數字或符號。忘記密碼可從 UART 輸入 <code>access</code> 查看。</p><div class="row"><button class="p" onclick="act(changePassword)">更改密碼</button><button onclick="setToken('')">登出此瀏覽器</button></div></section>
<section id="firmware" class="panel"><div class="panel-head"><div><p class="eyebrow">SYSTEM UPDATE</p><h2>韌體更新</h2><p>透過 OTA 更新這台裝置</p></div><span class="step">07</span></div>
<p>選擇 <b>esp32_clock.ino.bin</b>。更新前會暫停走時；完成後裝置重新啟動，位置與設定會保留。</p><div class="field" style="margin-top:18px"><label for="fw">韌體檔案（.bin）</label><input type="file" id="fw" accept=".bin"></div>
<div class="row form-action"><button class="d" onclick="ota()">上傳並更新</button></div><p class="hint">更新期間請保持供電。</p></section></div>
</div></div></main><div id="msg" class="ok" role="status" aria-live="polite" hidden>連線中…</div>
<script>
const $=i=>document.getElementById(i),pad=n=>String(n).padStart(2,'0');
const E={E_BUSY:'裝置忙碌，請先按「暫停走時」並等動作結束',E_TIME_INVALID:'尚無有效時間：請先連上 Wi-Fi 取得網路時間，或暫時用手機時間',E_MOTOR_TIMEOUT:'馬達轉動逾時，位置未知，請清除故障後重新歸零',
E_NOT_CALIBRATED:'尚未歸零，請先輸入時鐘實際顯示',E_RANGE:'數值超出範圍',E_FAULT:'系統故障，請先按「清除故障」',E_PLAN_STALE:'預覽已過期，請重試',
E_REVERSE_DISABLED:'目前只支援正向轉動',E_SAVE_THROTTLED:'5 秒內不能重複儲存，請稍後再試',E_NVS:'儲存失敗',
E_OTA_NO_PARTITION:'此韌體的分割表沒有 OTA 分區，需先用 UART 燒錄一次',E_OTA_IMAGE:'不是有效的 ESP32 韌體檔',E_OTA_WRITE:'寫入 Flash 失敗',
E_OTA_END:'映像驗證失敗',E_AUTH:'未授權'};
const ST={IDLE:'待命（自動走時中）',PAUSED:'已暫停',MOVING:'換頁中',NEEDS_TIME:'等待網路時間（請連上 Wi-Fi）',NEEDS_CALIBRATION:'需要歸零',
NEEDS_CATCHUP_CONFIRM:'需要確認補跑',FAULT:'故障'};
let S={},busyUi=false,V=null,lastV='',lastB=null,filled=false,TOKEN='';
let draftTouched=false,lastActualPlan='',lastDraftPlan='';
try{TOKEN=localStorage.getItem('flipToken')||''}catch(e){}
function setToken(t){TOKEN=t;try{if(t)localStorage.setItem('flipToken',t);else localStorage.removeItem('flipToken')}catch(e){}if(!t)showLogin(true)}
async function F(u,o){o=Object.assign({},o);o.headers={Authorization:'Bearer '+TOKEN};const r=await fetch(u,o);if(r.status==401){setToken('');throw new Error('請重新登入')}return r}
const fmt=(i,c)=>{c=c||S.cycle||720;const h=Math.floor(i/60);return(c==720?(h%12||12):pad(h))+':'+pad(i%60)};
const qText=q=>(q/1e6).toFixed(6);
function parseQDraft(){const raw=$('q').value.trim();if(!/^\d{1,5}(?:\.\d{1,6})?$/.test(raw))throw new Error('每分鐘步數需為 1–10000，最多 6 位小數');
const value=Number(raw);if(value<1||value>10000)throw new Error('每分鐘步數需為 1–10000');return Math.round(value*1e6)}
function stepPlan(q,remainder,count){const rows=[];let sum=0;for(let i=0;i<count;++i){const total=remainder+q,steps=Math.floor(total/1e6);
remainder=total%1e6;sum+=steps;rows.push({steps,remainder,carry:steps>Math.floor(q/1e6)})}return{rows,sum,remainder}}
function planHtml(q,remainder,start,cycle){const p=stepPlan(q,remainder,30);let h='<table class="plan"><thead><tr><th>換頁</th><th>半步</th><th>進位</th><th>換頁後餘數</th></tr></thead><tbody>';
for(let i=0;i<10;++i){const v=p.rows[i];h+='<tr><td>'+fmt((start+i+1)%cycle,cycle)+'</td><td>'+v.steps+'</td><td>'+(v.carry?'+1':'—')+'</td><td>'+v.remainder+'/1000000</td></tr>'}
return h+'</tbody></table><p>30 次換頁合計 '+p.sum+' 個半步；結束餘數 '+p.remainder+'/1000000 半步。</p>'}
function renderSteps(){if(!S.state)return;
$('qActive').textContent=qText(S.q)+' 半步/分鐘'+(S.savedQ===null||S.savedQ!==S.q?'（尚未儲存）':'');
$('qSaved').textContent=S.savedQ===null?'尚未儲存':qText(S.savedQ)+' 半步/分鐘';
$('remNow').textContent=S.remainder===null?'位置未知，無法推算':S.remainder+'/1000000 半步';
$('leftNow').textContent=S.busy&&S.left?S.left+' 個半步':'目前未移動';
const a=S.q+'|'+S.remainder+'|'+S.display+'|'+S.cycle+'|'+S.busy;
if(a!==lastActualPlan){lastActualPlan=a;$('planActive').innerHTML=S.remainder===null?'位置未知，請先完成歸零。':S.busy?'換頁或存檔進行中，完成後更新規劃。':planHtml(S.q,S.remainder,S.display,S.cycle)}
let draft,problem='';try{draft=parseQDraft()}catch(e){problem=e.message}
const d=problem+'|'+draft+'|'+S.q+'|'+$('ah').value+'|'+$('am').value;
if(d!==lastDraftPlan){lastDraftPlan=d;const box=$('planDraft');box.hidden=!problem&&draft===S.q;
if(problem)box.textContent=problem;
else if(draft!==S.q){const hour=+$('ah').value,minute=+$('am').value,start=Number.isInteger(hour)&&hour>=1&&hour<=12&&Number.isInteger(minute)&&minute>=0&&minute<60?(hour%12)*60+minute:0;
box.innerHTML='<h3>草稿試算：歸零後餘數 0</h3><p>以「歸零與套用步數」的顯示時間為起點。</p>'+planHtml(draft,0,start,720)}}}
function qDraftChanged(){draftTouched=true;renderSteps()}
function resetQDraft(){if(!S.state)return;draftTouched=false;$('q').value=qText(S.q);renderSteps()}
let noticeTimer=0;
const say=(t,bad)=>{const e=$('msg');e.textContent=t;e.className=bad?'bad':'ok';e.hidden=false;
clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>{e.hidden=true},bad?12000:8000)};
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
async function zero(){const h=+$('ah').value,m=+$('am').value,q=parseQDraft(),r=+$('rate').value,a=+$('accel').value;
if(!(Number.isInteger(h)&&h>=1&&h<=12&&Number.isInteger(m)&&m>=0&&m<=59))throw new Error('顯示時間不正確');
if(!(r>=10&&r<=1000&&a>=1&&a<=4000))throw new Error('速度需為 10–1000，加速度需為 1–4000');
await ensurePaused();await run('set_config',{values:{mechanics_confirmed:true,cycle_minutes:720,steps_per_page_u6:q,max_step_rate:r,acceleration:a}});
await run('set_display',{hour:h%12,minute:m,aligned:true});V=null;draftTouched=false;
await refresh();say('已記住目前顯示 '+h+':'+pad(m)+'。馬達沒有轉動；可直接儲存並開始走時')}
async function manualAdvance(n){if(!Number.isInteger(n)||n<1||n>8000)throw new Error('請輸入 1–8000 個整數半步');await ensurePaused();
const display=S.display,remainder=S.remainder,position=S.pos;say('馬達向前走 '+n+' 個半步…');await run('advance_steps',{steps:n});await idle(180000);
if(S.pos!==position||S.display!==display||S.remainder!==remainder)throw new Error('位置或餘步意外變更，請重新歸零');
say('已向前走 '+n+' 個半步；顯示位置與餘步不變')}
async function verify(n){if(!Number.isInteger(n)||n<1||n>720)throw new Error('分鐘數需為 1–720');await ensurePaused();const from=S.display;
say('前進 '+n+' 分鐘…');await run('advance_pages',{pages:n});await idle(600000);
if(!S.pos||S.display!=(from+n)%S.cycle)throw new Error('換頁中斷，位置未知，請重新歸零');V={from,to:S.display,n};say('請對照時鐘實際顯示')}
async function saveOnly(){await ensurePaused();await run('save_config');await idle(30000);if(S.dirty)throw new Error('儲存失敗，請稍候 5 秒再試');say('設定已永久儲存')}
function aroundMin(){return Math.ceil((S.cycle-S.ahead)*(S.q/1e6)/S.rate/60)+1}
async function startWalking(){const p=await run('preview_sync');await run('resume',{plan_id:p.plan_id,confirm_large:true});await refresh();return p}
async function goAround(){const n=S.cycle-S.ahead;if(!confirm('往前轉 '+n+' 分鐘到目前時間，約 '+aroundMin()+' 分鐘？'))return;await ensurePaused();
say('轉一圈對時中…');await run('advance_pages',{pages:n});await idle(1800000);if(!S.pos)throw new Error('換頁中斷，位置未知，請重新歸零');await startWalking();say('已對時，開始自動走時')}
async function finish(){await ensurePaused();await run('set_config',{values:{mechanics_confirmed:true}});await run('save_config');await idle(30000);
if(S.dirty)throw new Error('儲存失敗，請稍候 5 秒再試');await startWalking();
say(S.ahead?'已儲存。顯示比目前時間快 '+S.ahead+' 分鐘，時鐘會等時間追上後才開始走':'已儲存，正在轉到目前時間，之後自動走時')}
const WE={E_WIFI_AUTH:'密碼錯誤或被拒絕',E_WIFI_NOT_FOUND:'找不到這個 Wi-Fi',E_WIFI_TIMEOUT:'連線逾時',E_WIFI_SAVE:'連上了但儲存失敗',
E_WIFI_SSID:'請輸入 Wi-Fi 名稱',E_WIFI_NO_SAVED:'尚未儲存 Wi-Fi',E_WIFI_PASSWORD:'密碼需 8–64 個字元（開放網路請留空）',E_BUSY:'上一個操作還在進行中'};
let W={trial:{},networks:[]},wifiBusy=false;
function whyText(n){if(!n)return'分享器沒有回應，可能是訊號太弱';if([2,15,16,202,204].includes(n))return'分享器拒絕交握，多半是密碼錯誤（原因 '+n+'）';
if([201,210,211,212].includes(n))return'找不到這個 2.4 GHz 網路，請核對名稱並靠近分享器（原因 '+n+'）';return'訊號不穩或分享器沒回應（原因 '+n+'）'}
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
function renderWifi(){const s=W.sta||{},mode=W.connectionMode;
$('wst').textContent=s.connected?('已連線 '+(s.ssid||W.saved||'')+'　'+(s.ip||'')+'（'+s.rssi+' dBm）'):
mode=='manual_trial'?'正在手動測試連線，最長約 45 秒；熱點可能短暫中斷':
mode=='trying_saved'?('正在嘗試已儲存的「'+W.saved+'」，最多約 60 秒；若收不到就保持裝置熱點供設定'):
mode=='setup'?('舊網路「'+W.saved+'」目前連不上；已停止背景重試，裝置熱點保持開啟。可設定新網路或手動重試'+(W.why?'。上次失敗：'+whyText(W.why):'')):
'未設定，裝置熱點保持開啟';
$('wifiStatus').className='connection-status '+(s.connected?'connected':mode=='trying_saved'||mode=='manual_trial'?'trial':'setup');
$('bRetrySaved').disabled=wifiBusy||!W.saved||s.connected||mode=='manual_trial'||W.scanning;lanBox();
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
if(W.trial.state=='ok'){$('wpw').value='';say('已連上「'+W.trial.ssid+'」並儲存。請看上方綠框的區網網址，讓手機連到同一個 Wi-Fi 後開啟');$('wlan').scrollIntoView({behavior:'smooth',block:'center'})}else throw new Error('連線失敗：'+(WE[W.trial.reason]||W.trial.reason)+'。'+whyText(W.why)+'。未儲存')}
catch(e){say(e.message,1)}wifiBusy=false;renderWifi()}
async function wifiRetrySaved(){if(wifiBusy||!W.saved)return;wifiBusy=true;
try{say('重試已儲存的「'+W.saved+'」，最長約 45 秒。這次手動嘗試可能暫時中斷裝置熱點');
const j=await wifiPost({op:'retry_saved'});if(!j.ok)throw new Error(WE[j.error]||j.error);
const done=await wifiWait(120000,()=>W.trial&&W.trial.state!='running');if(!done)throw new Error('等不到結果，請重新整理頁面確認');
if(W.trial.state=='ok')say('已重新連上「'+W.saved+'」；原設定保持不變');
else throw new Error('仍無法連上「'+W.saved+'」：'+(WE[W.trial.reason]||W.trial.reason)+'。裝置熱點會保持開啟，可設定新網路')}
catch(e){say(e.message,1)}wifiBusy=false;renderWifi()}
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
const wn=W.connectionMode=='trying_saved'?'正在連線「'+W.saved+'」':W.connectionMode=='setup'?'裝置熱點設定中':'';
$('disp').textContent=S.pos?fmt(S.display):'位置未知';$('st').textContent=(S.state=='NEEDS_TIME'&&W.saved?(wn||'已連上 Wi-Fi')+'，等待網路時間':S.state=='IDLE'&&S.ahead?'等時間追上（顯示快 '+S.ahead+' 分鐘）':(ST[S.state]||S.state))+(S.err?'　'+S.err:'');
$('stateDot').className='state-dot '+(S.state=='FAULT'||!S.pos?'bad':S.state=='IDLE'||S.state=='MOVING'?'good':'');
$('rt').textContent=S.rtc?new Date((S.utc+S.off*60)*1000).toISOString().replace('T',' ').slice(0,19):W.connectionMode=='trying_saved'?'取得中…':'尚未取得（請連上 Wi-Fi）';
$('ps').textContent=S.pos?(S.mech?'已歸零':'未確認機構'):'未知';
$('sv').textContent=S.snap?(fmt(S.snapDisplay)+(S.dirty?'（有未儲存變更）':'')):'尚無';
const bh=(S.restoring?'<p>開機自動恢復：取得網路時間後，會補跑到目前時間。</p>':'')+
(S.syncAsk?'<p>網路時間與目前時間差異超過 5 分鐘。<button onclick="act(confirmSync)">確認用網路時間校時</button></p>':'')+
(S.ahead&&!S.busy?'<p>時鐘只能往前轉。顯示比目前時間快 '+S.ahead+' 分鐘，所以會先停著，'+S.ahead+' 分鐘後才開始走。不想等可以轉一整圈對時（約 '+aroundMin()+' 分鐘）。</p><div class="row"><button id="bGoAround" onclick="act(goAround)">現在轉一圈對時</button></div>':'');
if(bh!==lastB){$('banner').innerHTML=bh;lastB=bh}
const idle_=!S.busy&&!busyUi;
$('bPause').disabled=S.paused&&!S.busy;$('bClear').disabled=!S.fault;
if(!draftTouched&&$('q').value!==qText(S.q))$('q').value=qText(S.q);
if(!filled){filled=true;$('rate').value=S.rate;$('accel').value=S.accel}
renderSteps();
document.querySelectorAll('#app section button').forEach(b=>{if(!b.closest('#wifi')&&b.id!='bPause'&&b.id!='bClear'&&b.id!='bStop')b.disabled=!idle_});
const ready=idle_&&S.pos&&S.mech;for(const id of['bVerify','bSave','bFinish'])$(id).disabled=!ready;
document.querySelectorAll('.tq').forEach(b=>b.disabled=!ready);
let h='';if(V){h='<p>已從 <b>'+fmt(V.from)+'</b> 前進 '+V.n+' 分鐘，應該顯示 <b>'+fmt(V.to)+'</b>。</p><p>不對的話，回到歸零區輸入實際顯示的時間，再調整偏移。</p>'}
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
