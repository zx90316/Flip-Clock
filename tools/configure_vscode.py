"""Generate portable VS Code task and launch configurations."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
VSC = ROOT / '.vscode'
VSC.mkdir(exist_ok=True)
definitions = [
    ('Flip：主控操作台', 'dev', ['menu']),
    ('Flip：檢查環境', 'dev', ['doctor']),
    ('Flip：準備桌面操作工具', 'dev', ['desktop-setup']),
    ('Flip：安裝編譯環境', 'build', ['setup']),
    ('Flip：列出連接埠', 'dev', ['ports']),
    ('Flip：建置 Uno', 'build', ['build','--board','uno_motor']),
    ('Flip：建置 ESP32-CAM', 'build', ['build','--board','esp32_clock']),
    ('Flip：建置兩板', 'build', ['build']),
    ('Flip：執行全部軟體測試', 'build', ['test']),
    ('Uno：燒錄並驗證（單板 USB）', 'dev', ['upload','--board','uno_motor']),
    ('Uno：讀取安全待機狀態', 'dev', ['uno-status']),
    ('Uno：單顆空載試轉 16 半步（需先接線）', 'dev', ['bench','--steps','16','--rate','30']),
    ('Uno：序列維修台', 'dev', ['monitor','--board','uno_motor']),
    ('Uno：堆疊分析', 'analyze_uno_stack', []),
    ('ESP：燒錄並驗證（Uno UART 模式）', 'dev', ['upload','--board','esp32_clock']),
    ('ESP：序列維修台', 'dev', ['monitor','--board','esp32_clock']),
    ('ESP：開啟 BLE 配對窗口', 'dev', ['pair']),
    ('ESP：設定 Wi-Fi（密碼不顯示）', 'dev', ['wifi']),
    ('ESP：設定 NTP 伺服器', 'dev', ['monitor','--board','esp32_clock','--initial','ntp ${input:ntpServers}']),
    ('ESP：清除 BLE bond（本地維修）', 'dev', ['monitor','--board','esp32_clock','--initial','clear_bonds CONFIRM']),
    ('ESP：清除已保存設定（本地維修，RTC 保留）', 'dev', ['monitor','--board','esp32_clock','--initial','reset_config CONFIRM']),
    ('BLE：掃描裝置', 'dev', ['ble-scan']),
    ('BLE：互動主控台', 'dev', ['ble']),
    ('BLE：讀取狀態', 'dev', ['ble-op','--op','get_status']),
    ('BLE：讀取設定', 'dev', ['ble-op','--op','get_config']),
    ('BLE：以電腦現在時間校時', 'dev', ['ble-time']),
    ('BLE：設定實際顯示（確認完整落頁）', 'dev', ['ble-op','--op','set_display','--values','{"hour":${input:hour},"minute":${input:minute},"aligned":true}']),
    ('BLE：微調半步', 'dev', ['ble-op','--op','jog_steps','--values','{"steps":${input:steps}}']),
    ('BLE：前進整頁', 'dev', ['ble-op','--op','advance_pages','--values','{"pages":${input:pages}}']),
    ('BLE：修改 RAM 設定', 'dev', ['ble-op','--op','set_config','--values','{"values":${input:configValues}}']),
    ('BLE：保存設定', 'dev', ['ble-op','--op','save_config']),
    ('BLE：追趕預覽', 'dev', ['ble-op','--op','preview_sync']),
    ('BLE：依 plan_id 恢復走時', 'dev', ['ble-op','--op','resume','--values','{"plan_id":${input:planId},"confirm_large":${input:confirmLarge}}']),
    ('BLE：暫停（完成當頁）', 'dev', ['ble-op','--op','pause']),
    ('BLE：立即停止（位置需重新確認）', 'dev', ['ble-op','--op','stop']),
    ('BLE：清除故障', 'dev', ['ble-op','--op','clear_fault']),
    ('BLE：確認大幅網路校時', 'dev', ['ble-op','--op','confirm_time','--values','{"utc_s":${input:pendingSync}}']),
    ('Flip：重新產生 VS Code 設定', 'configure_vscode', []),
    ('Flip：打包工程', 'package', []),
]
tasks = []
for title, script, args in definitions:
    task = {'label':title,'type':'process','command':'python',
            'args':['-u','${workspaceFolder}/tools/'+script+'.py',*args],
            'options':{'cwd':'${workspaceFolder}','env':{'PYTHONUTF8':'1','PYTHONUNBUFFERED':'1'}},
            'presentation':{'reveal':'always','panel':'dedicated','clear':False,'focus':True},
            'problemMatcher':['$gcc'] if script=='build' else []}
    if title=='Flip：建置兩板': task['group']={'kind':'build','isDefault':True}
    if title=='Flip：執行全部軟體測試': task['group']={'kind':'test','isDefault':True}
    tasks.append(task)
inputs = [{'id':key,'type':'promptString','description':description,'default':default} for key,description,default in [
    ('hour','實物目前顯示小時 0–23；僅完整落頁後確認','10'),
    ('minute','實物目前顯示分鐘 0–59','30'),('steps','微調半步數（正式版僅正向 1–256）','4'),
    ('pages','前進頁數 1–60','1'),('configValues','設定物件 JSON；先修改 RAM，再另行保存','{"mechanics_confirmed":true,"cycle_minutes":720}'),
    ('planId','最新追趕預覽中的 plan_id，須在 30 秒內使用',''),
    ('pendingSync','狀態中 pending_sync_utc 的實際整數值',''),
    ('ntpServers','NTP 設定 JSON','{"servers":["pool.ntp.org","time.cloudflare.com","time.google.com"]}')]]
inputs.append({'id':'confirmLarge','type':'pickString','description':'是否明確允許超限的向前追趕？','options':['false','true'],'default':'false'})
(VSC/'tasks.json').write_text(json.dumps({'version':'2.0.0','tasks':tasks,'inputs':inputs},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
launches = []
for title,script,args in definitions:
    if '${input:' in ' '.join(args) or script not in {'dev','build'}: continue
    if title not in {'Flip：主控操作台','Flip：檢查環境','Flip：建置兩板','Flip：執行全部軟體測試',
                     'Uno：燒錄並驗證（單板 USB）','Uno：讀取安全待機狀態','Uno：序列維修台',
                     'ESP：燒錄並驗證（Uno UART 模式）','ESP：序列維修台','ESP：開啟 BLE 配對窗口',
                     'ESP：設定 Wi-Fi（密碼不顯示）','BLE：互動主控台'}: continue
    launches.append({'name':title,'type':'debugpy','request':'launch',
        'program':'${workspaceFolder}/tools/'+script+'.py','args':args,'cwd':'${workspaceFolder}',
        'console':'integratedTerminal','justMyCode':True,'env':{'PYTHONUTF8':'1','PYTHONUNBUFFERED':'1'}})
(VSC/'launch.json').write_text(json.dumps({'version':'0.2.0','configurations':launches},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(VSC/'settings.json').write_text(json.dumps({'python.defaultInterpreterPath':'python','python.terminal.activateEnvironment':False,
    'files.associations':{'*.ino':'cpp'},'files.encoding':'utf8','terminal.integrated.defaultProfile.windows':'PowerShell',
    'files.exclude':{'**/.tools':True,'**/.build':True,'**/.local':True,'**/__pycache__':True},
    'search.exclude':{'**/.tools':True,'**/.build':True,'**/dist':True},
    'C_Cpp.default.compileCommands':'${workspaceFolder}/.build/esp32_clock/compile_commands.json'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(VSC/'extensions.json').write_text(json.dumps({'recommendations':['ms-python.python','ms-python.debugpy','ms-vscode.cpptools']},indent=2)+'\n',encoding='utf-8')
print(f'Generated {len(tasks)} tasks and {len(launches)} launch configurations.')
