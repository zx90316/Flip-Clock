// Execute the firmware's embedded page script against a small DOM in Node.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const page = fs.readFileSync(path.join(__dirname, '..', 'firmware', 'esp32_clock', 'web_page.h'), 'utf8');
const ids = [...page.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
assert.equal(new Set(ids).size, ids.length, 'HTML ids must be unique');
for (const anchor of ['overview', 'motion', 'setup', 'wifi', 'account', 'firmware']) {
  assert.match(page, new RegExp(`href="#${anchor}"`));
  assert.ok(ids.includes(anchor), `navigation target #${anchor} is missing`);
}
assert.ok(page.indexOf('id="bFinish"') < page.indexOf('id="bVerify"'), 'direct save must appear before optional movement check');
assert.ok(ids.includes('manualSteps') && !ids.includes('trim'), 'manual stepping replaces saved trim controls');
const script = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    id, value: '', textContent: '', innerHTML: '', hidden: false, disabled: false,
    className: '', dataset: {}, style: {}, scrollIntoView() {}, closest: () => null
  });
  return elements.get(id);
}
const document = { getElementById: element, querySelectorAll: selector =>
  selector === '#app section button' ? ['bSave', 'bFinish', 'bGoAround'].map(element) : [] };
const localStorage = { getItem: () => '', setItem() {}, removeItem() {} };
const context = vm.createContext({ document, localStorage, console, setTimeout: () => 1, clearTimeout() {} });
// The final polling loop needs a real device; test the page's functions before it starts.
vm.runInContext(script.slice(0, script.indexOf('if(TOKEN)showLogin')), context);
const run = code => vm.runInContext(code, context);

const thirty = run('stepPlan(136533333,0,30)');
assert.equal(thirty.sum, 4095);
assert.equal(thirty.remainder, 999990);
assert.equal(thirty.rows[0].steps, 136);
assert.equal(thirty.rows[1].steps, 137);
assert.equal(thirty.rows[1].carry, true);

element('ah').value = '12'; element('am').value = '0';
run("S={state:'PAUSED',fw:'0.4.7',q:136533333,savedQ:136533333,remainder:0,display:0,cycle:720,pos:true,mech:true,busy:false,left:0,paused:true,fault:false,rtc:false,snap:false,dirty:false,gen:1,trim:0,rate:200,accel:100,ahead:0,syncAsk:false}; W={trial:{},networks:[],saved:'Home',connectionMode:'setup',sta:{connected:false}}; render()");
assert.match(element('qActive').textContent, /136\.533333/);
assert.match(element('planActive').innerHTML, /30 次換頁合計 4095/);
run('renderWifi()');
assert.match(element('wst').textContent, /熱點保持開啟/);
assert.match(element('wifiStatus').className, /setup/);

element('q').value = '137'; run('qDraftChanged()');
assert.equal(run('S.q'), 136533333); // editing is only a draft
assert.equal(element('planDraft').hidden, false);
assert.match(element('planDraft').innerHTML, /30 次換頁合計 4110/);
element('q').value = '0'; run('qDraftChanged()');
assert.match(element('planDraft').textContent, /1–10000/);
run('resetQDraft()'); assert.equal(element('q').value, '136.533333');

run('S.q=137000000; S.savedQ=136533333; S.dirty=true; render()');
assert.equal(element('bSave').disabled, false);
assert.equal(element('bFinish').disabled, false);
assert.match(element('qActive').textContent, /尚未儲存/);

run('S.busy=true; S.left=42; renderSteps()');
assert.match(element('leftNow').textContent, /42/);
assert.match(element('planActive').innerHTML, /完成後更新/);
run('S.busy=false; S.pos=false; S.remainder=null; renderSteps()');
assert.match(element('remNow').textContent, /位置未知/);
assert.match(element('planActive').innerHTML, /位置未知/);

run("S.pos=true; S.mech=true; S.remainder=123; S.display=480; S.snap=true; S.snapDisplay=480; S.gen=42; S.dirty=false; S.busy=false; S.ahead=0; render()");
assert.equal(element('sv').textContent, '8:00');
run("calls=[]; ensurePaused=async()=>{}; run=async (op,args)=>{calls.push([op,args]); return op==='preview_sync'?{plan_id:7}:{}}; idle=async()=>{S.dirty=false}; refresh=async()=>{}");
run('manualAdvance(8)').then(() => {
  assert.equal(run('S.display'), 480);
  assert.equal(run('S.remainder'), 123);
  assert.equal(run('S.dirty'), false);
  assert.equal(run('calls[0][0]'), 'advance_steps');
  assert.equal(run('calls[0][1].steps'), 8);
  run('calls=[]; S.dirty=true');
  return run('finish()');
}).then(() => {
  assert.deepEqual(Array.from(run('calls')).map(call => call[0]), ['set_config', 'save_config', 'preview_sync', 'resume']);
  console.log('PASS web UI: step plan, one-time advance, snapshot, direct save/start');
}).catch(error => { console.error(error); process.exitCode = 1; });
