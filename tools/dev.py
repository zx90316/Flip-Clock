#!/usr/bin/env python3
"""VS Code/terminal control entry point. Connecting never arms or moves a motor."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/settings.json'
sys.path.insert(0, str(ROOT / '.tools/client'))

def settings():
    return json.loads(LOCAL.read_text(encoding='utf-8')) if LOCAL.exists() else {}

def save_settings(value):
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    temp = LOCAL.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temp.replace(LOCAL)

def run(args, env=None):
    subprocess.run([str(x) for x in args], cwd=ROOT, env=env, check=True)

def serial_module():
    try:
        import serial
        return serial
    except ImportError:
        raise RuntimeError('請先執行「Flip：準備桌面操作工具」。') from None

def ports():
    serial_module()
    from serial.tools import list_ports
    return list(list_ports.comports())

def choose_port(board, supplied=None):
    if supplied:
        return supplied
    values = ports()
    chosen = settings().get(board + '_port')
    if chosen and any(p.device == chosen for p in values):
        return chosen
    if len(values) == 1:
        return values[0].device
    if not values:
        raise RuntimeError('找不到序列埠，請用 USB 接上目前要操作的板子。')
    for i, p in enumerate(values, 1):
        print(f'{i}. {p.device}: {p.description}')
    try:
        selected = int(input('選擇連接埠編號：')) - 1
        if selected < 0 or selected >= len(values):
            raise ValueError
    except ValueError:
        raise RuntimeError('未選擇有效的連接埠。') from None
    config = settings()
    config[board + '_port'] = values[selected].device
    save_settings(config)
    return values[selected].device

def open_serial(board, supplied=None):
    serial = serial_module()
    port = choose_port(board, supplied)
    # Set lines before opening; some USB drivers can still pulse DTR. Always pause before maintenance.
    device = serial.Serial(port=None, baudrate=115200, timeout=0.1, write_timeout=2)
    device.dtr = False
    device.rts = False
    device.port = port
    try:
        device.open()
    except serial.SerialException as error:
        raise RuntimeError(f'{port} 無法開啟；請先結束其他監控或燒錄視窗。{error}') from None
    print(f'已開啟 {port}，115200。維修前應先 pause。', flush=True)
    return device

def monitor(board, supplied=None, initial=None):
    with open_serial(board, supplied) as device:
        print('輸入一行後 Enter 送出；/quit 結束。Ctrl+C 亦可關閉。', flush=True)
        done = threading.Event()
        def reader():
            while not done.is_set():
                raw = device.readline()
                if raw:
                    print(raw.decode('utf-8', errors='replace').rstrip(), flush=True)
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        if initial:
            device.write(initial.encode('utf-8') + b'\n')
        try:
            while True:
                line = input()
                if line.strip() == '/quit':
                    return
                device.write(line.encode('utf-8') + b'\n')
        finally:
            done.set()
            thread.join(timeout=1)

def wifi(supplied=None):
    print('ESP 必須已接上序列轉接並正常開機，馬達斷電。')
    ssid = input('2.4 GHz Wi-Fi 名稱：')
    password = getpass.getpass('Wi-Fi 密碼（不顯示、不保存到檔案）：')
    if not 1 <= len(ssid.encode('utf-8')) <= 32 or len(password.encode('utf-8')) > 64:
        raise ValueError('SSID／密碼長度超出支援範圍。')
    line = 'wifi ' + json.dumps({'ssid': ssid, 'password': password}, ensure_ascii=False, separators=(',', ':'))
    with open_serial('esp32_clock', supplied) as device:
        device.write(line.encode('utf-8') + b'\n')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            text = device.readline().decode('utf-8', errors='replace').strip()
            if text:
                print(text)
            if text == 'WIFI_SAVED':
                return
        raise RuntimeError('未收到 WIFI_SAVED，請確認 ESP 已正常開機及接線模式。')

def ble(op=None, values=None):
    args = [sys.executable, ROOT / 'tools/ble_client.py']
    address = settings().get('ble_address')
    if address:
        args += ['--address', address]
    if op:
        args += ['--op', op, '--values', json.dumps(values or {}, ensure_ascii=False)]
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT / '.tools/client') + os.pathsep + env.get('PYTHONPATH', '')
    env['PYTHONUTF8'] = '1'
    run(args, env)

def doctor():
    print('專案：', ROOT)
    print('Python：', sys.executable)
    cli = ROOT / '.tools/cli/arduino-cli.exe'
    if not cli.exists():
        print('尚未準備編譯環境，請執行「Flip：安裝編譯環境」。')
    else:
        import build
        build.shorten_windows_paths()
        build.run([build.cli(), 'version'])
        build.run([build.cli(), 'core', 'list', '--no-color'])
    try:
        for port in ports():
            print(port.device, port.description, f'VID={port.vid!r} PID={port.pid!r}')
    except RuntimeError as error:
        print(error)
    print('詳細接線：docs/bringup.md；已知硬體進度：docs/hardware/progress.md')

def menu():
    actions = [
        ('檢查環境及連接埠', lambda: doctor()),
        ('建置韌體', lambda: run([sys.executable, ROOT/'tools/build.py', 'build'])),
        ('執行軟體測試', lambda: run([sys.executable, ROOT/'tools/build.py', 'test'])),
        ('燒錄 ESP32-CAM（序列救援；平常用網頁 OTA）', lambda: upload('esp32_clock')),
        ('ESP 序列維修台', lambda: monitor('esp32_clock')),
        ('ESP 開啟 120 秒 BLE 配對窗口', lambda: monitor('esp32_clock', initial='pair')),
        ('ESP 設定 Wi-Fi', lambda: wifi()),
        ('BLE 掃描裝置', lambda: run_ble_scan()),
        ('BLE 主控台（狀態／校時／校準／暫停／停止／保存）', lambda: ble()),
        ('BLE 讀取狀態', lambda: ble('get_status')),
        ('BLE 以電腦現在時間校時', lambda: ble('set_time', {'utc_s': int(time.time())})),
        ('BLE 暫停（當頁完成）', lambda: ble('pause')),
        ('BLE 立即停止（位置將重新確認）', lambda: ble('stop')),
        ('BLE 保存設定', lambda: ble('save_config')),
    ]
    while True:
        print('\nFlip-Clock 主控操作台')
        for i, (title, _) in enumerate(actions, 1):
            print(f'{i:2}. {title}')
        print(' 0. 結束')
        try:
            choice = int(input('選擇：'))
            if choice == 0:
                return
            if choice < 1 or choice > len(actions):
                raise ValueError
            actions[choice - 1][1]()
        except (ValueError, RuntimeError, subprocess.CalledProcessError) as error:
            print('操作未完成：', error)

def upload(board, supplied=None):
    port = choose_port(board, supplied)
    print('序列燒錄：馬達斷電、接好序列轉接、ESP IO0→GND 後按 RST（見 docs/wiring.md）。', flush=True)
    run([sys.executable, ROOT/'tools/build.py', 'upload', '--board', board, '--port', port])

def run_ble_scan():
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT / '.tools/client') + os.pathsep + env.get('PYTHONPATH', '')
    env['PYTHONUTF8'] = '1'
    run([sys.executable, ROOT/'tools/ble_client.py', '--scan'], env)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['menu','doctor','desktop-setup','ports','upload','monitor','pair','wifi','ble','ble-scan','ble-time','ble-op'])
    parser.add_argument('--board', choices=['esp32_clock'], default='esp32_clock')
    parser.add_argument('--port')
    parser.add_argument('--op')
    parser.add_argument('--values', default='{}')
    parser.add_argument('--initial', help='One initial UART line, then interactive maintenance console')
    args = parser.parse_args()
    if args.action == 'menu': menu()
    elif args.action == 'doctor': doctor()
    elif args.action == 'desktop-setup':
        run([sys.executable,'-m','pip','install','--target',ROOT/'.tools/client','-r',ROOT/'tools/requirements-windows.lock.txt','-r',ROOT/'tools/requirements-serial.txt'])
    elif args.action == 'ports':
        for port in ports(): print(port.device,port.description)
    elif args.action == 'upload': upload(args.board,args.port)
    elif args.action == 'monitor': monitor(args.board,args.port,args.initial)
    elif args.action == 'pair': monitor('esp32_clock',args.port,'pair')
    elif args.action == 'wifi': wifi(args.port)
    elif args.action == 'ble-scan': run_ble_scan()
    elif args.action == 'ble': ble()
    elif args.action == 'ble-time': ble('set_time',{'utc_s':int(time.time())})
    elif args.action == 'ble-op':
        if not args.op: parser.error('--op is required')
        ble(args.op,json.loads(args.values))

if __name__ == '__main__':
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    from process_lifetime import configure_process_lifetime
    _job = configure_process_lifetime()
    try: main()
    except KeyboardInterrupt: print('\n操作已結束；連接埠已釋放。')
    except (RuntimeError,ValueError,subprocess.CalledProcessError) as error:
        print('操作未完成：',error,file=sys.stderr)
        raise SystemExit(1)
