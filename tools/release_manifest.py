"""Record source provenance, exact versions and generated firmware identities."""
import csv
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
data = {
    'project': 'ESP32-CAM single-motor split-flap clock', 'version': '0.4.3', 'protocol': 1,
    'license': 'GPL-3.0-only', 'hardware_validation': '0.4.3 single-controller build not yet run on hardware; see docs/hardware/progress.md',
    'upstream': {'url': 'https://github.com/zx90316/split-flap', 'ref': 'esp32-purchased-bom',
                 'commit': 'f4216b735131ca2adf7772f3dbfca01d22112111'},
    'specification': {'file': 'docs/engineering-spec.zh-TW.md', 'version': '2.0 / 2026-10-31',
                      'sha256': sha(ROOT / 'docs/engineering-spec.zh-TW.md')},
    'toolchain': [
        {'name': 'Arduino CLI', 'version': '1.5.1', 'source': 'https://github.com/arduino/arduino-cli', 'license': 'GPL-3.0'},
        {'name': 'Arduino-ESP32', 'version': '3.3.12', 'source': 'https://github.com/espressif/arduino-esp32', 'license': 'LGPL-2.1'},
        {'name': 'ESP-IDF bundled with core', 'version': 'as locked by Arduino-ESP32 3.3.12', 'source': 'https://github.com/espressif/esp-idf', 'license': 'Apache-2.0'},
        {'name': 'NimBLE-Arduino', 'version': '2.5.1', 'source': 'https://github.com/h2zero/NimBLE-Arduino', 'license': 'Apache-2.0',
         'local_patch': 'tools/harden_ble.py: reject automatic replacement of existing bond; UART clear_bonds required',
         'upstream_server_sha256': 'af4335cf6b9e5ca3be63770307736fe50d29b53529c0dd3579f7ed515b553895',
         'patched_server_sha256': sha(ROOT / '.tools/user/libraries/NimBLE-Arduino/src/NimBLEServer.cpp'),
         'build_defines': ['MYNEWT_VAL_BLE_SM_SC_ONLY=1']},
        {'name': 'cJSON (host tests)', 'version': '1.7.19', 'source': 'https://github.com/DaveGamble/cJSON', 'license': 'MIT'},
        {'name': 'Zig (host tests)', 'version': '0.13.0', 'source': 'https://ziglang.org', 'license': 'MIT; bundled toolchain licenses apply'},
        {'name': 'Bleak (acceptance client)', 'version': '3.0.1', 'source': 'https://github.com/hbldh/bleak', 'license': 'MIT',
         'windows_lock': 'tools/requirements-windows.lock.txt', 'wheel_sha256': 'docs/client-dependencies.json'},
    ],
    'runtime_defaults': {'motor_step_rate_cap': 1000, 'reverse': False, 'mechanics_confirmed': False,
                         'recovery_policy': 'RESTORE_SAVED_POSITION', 'auto_run_after_boot': True, 'ota': True},
    'firmware': {board: json.loads((ROOT / 'dist' / board / 'manifest.json').read_text(encoding='utf-8'))
                 for board in ['esp32_clock']},
    'compiled_source_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for folder in ['firmware', 'shared/protocol/src']
                               for p in sorted((ROOT / folder).rglob('*')) if p.is_file()},
    'verification': {'report': 'docs/host-tests.txt', 'physical_tests': 'docs/hardware-acceptance.csv'}
}
(ROOT / 'manifest.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
names = ['LM2596 輸出 5.0V 及接線', '30 次冷啟動：可開機且無意外連續轉動', '開機時 IO12-15 造成的馬達抖動與步數誤差',
         '半步相序及輸出關閉', '900 步/秒、400 步/秒² 帶負載不漏步', 'Wi-Fi/網頁/掃描進行中走時平順',
         'Wi-Fi＋馬達動作時電壓及溫升', 'stop <=100ms / pause 當段完成', '不同工作階段及 NVS 寫入時掉電',
         '斷電重啟後取得網路時間並補跑', '24 小時斷網恢復', '完整週期及 72 小時走時',
         '網頁登入、改密碼、OTA 斷網/斷電', 'Android/iOS 配對及未授權拒絕', 'BLE 重送/斷線/最低 MTU']
if not (ROOT / 'docs/hardware-acceptance.csv').exists():
    with (ROOT / 'docs/hardware-acceptance.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'test', 'status', 'firmware_sha256', 'date', 'board_motor', 'parameters',
                         'voltage_current_temperature', 'observed_result', 'evidence', 'operator'])
        for i, name in enumerate(names, 1):
            writer.writerow([f'H{i:02}', name, '未執行', '', '', '', '', '', '', '', ''])
print('Manifest and blank hardware acceptance log written.')
