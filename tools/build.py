#!/usr/bin/env python3
"""Isolated, pinned build. No serial device is opened except by upload/monitor/ports."""
import argparse
import atexit
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / '.tools'
CLI_VERSION = '1.5.1'
INDEX = 'https://espressif.github.io/arduino-esp32/package_esp32_index.json'
BOARDS = {'esp32_clock': 'esp32:esp32:esp32cam:PartitionScheme=min_spiffs,FlashFreq=40'}
SHORT_ROOT = ROOT

def shorten_windows_paths():
    """Official GCC contains paths exceeding MAX_PATH in this workspace; map temporarily."""
    global SHORT_ROOT
    if os.name != 'nt' or len(str(ROOT)) < 70:
        return
    for drive in ['X:', 'Y:', 'Z:', 'W:', 'V:', 'U:', 'T:']:
        if Path(drive + '/').exists():
            continue
        p = subprocess.run(['subst', drive, str(ROOT)], capture_output=True)
        if p.returncode == 0:
            SHORT_ROOT = Path(drive + '/')
            atexit.register(lambda d=drive: subprocess.run(['subst', d, '/D'], capture_output=True))
            return
    raise RuntimeError('A free drive letter is needed to shorten Windows compiler paths.')

def short(value):
    return str(value).replace(str(ROOT), str(SHORT_ROOT).rstrip('\\/'))

def environment():
    env = os.environ.copy()
    for name, directory in [('DATA', 'data'), ('DOWNLOADS', 'downloads'), ('USER', 'user')]:
        env['ARDUINO_DIRECTORIES_' + name] = short(TOOLS / directory)
    env['ARDUINO_UPDATER_ENABLE_NOTIFICATION'] = 'false'
    env['PYTHONUTF8'] = '1'
    env['PYTHONUNBUFFERED'] = '1'
    return env

def cli():
    return str(TOOLS / 'cli' / ('arduino-cli.exe' if os.name == 'nt' else 'arduino-cli'))

def run(args, log=None, interactive=False):
    command = [short(a) for a in args]
    if interactive:
        subprocess.run(command, env=environment(), cwd=ROOT, check=True)
        return
    lines = []
    with subprocess.Popen(command, env=environment(), cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1) as process:
        for line in process.stdout:
            line = line.replace(str(SHORT_ROOT).rstrip('\\/') + '\\', str(ROOT) + '\\') if SHORT_ROOT != ROOT else line
            print(line, end='', flush=True)
            lines.append(line)
        code = process.wait()
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        Path(log).write_text(''.join(lines), encoding='utf-8')
    if code:
        raise subprocess.CalledProcessError(code, command)

def setup():
    if not Path(cli()).exists():
        if os.name != 'nt':
            raise RuntimeError('Install Arduino CLI 1.5.1 into .tools/cli on this OS.')
        base = f'https://github.com/arduino/arduino-cli/releases/download/v{CLI_VERSION}/'
        name = f'arduino-cli_{CLI_VERSION}_Windows_64bit.zip'
        data = urllib.request.urlopen(base + name, timeout=60).read()
        checks = urllib.request.urlopen(base + CLI_VERSION + '-checksums.txt', timeout=60).read().decode()
        expected = next(line.split()[0] for line in checks.splitlines() if line.endswith(name))
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError('CLI checksum mismatch')
        TOOLS.mkdir(parents=True, exist_ok=True)
        archive = TOOLS / name
        archive.write_bytes(data)
        with zipfile.ZipFile(archive) as z:
            z.extract('arduino-cli.exe', TOOLS / 'cli')
    run([cli(), 'version'])
    run([cli(), 'core', 'update-index', '--additional-urls', INDEX])
    run([cli(), 'core', 'install', 'esp32:esp32@3.3.12', '--additional-urls', INDEX])
    run([cli(), 'lib', 'install', 'NimBLE-Arduino@2.5.1'])
    if not (TOOLS / 'host/ziglang').exists():
        run([sys.executable, '-m', 'pip', 'install', '--target', TOOLS / 'host', 'ziglang==0.13.0'])
    run([sys.executable, ROOT / 'tools/prepare_test.py'])

def build(board):
    out = ROOT / 'dist' / board
    out.mkdir(parents=True, exist_ok=True)
    build_path = ROOT / '.build' / board
    flags = []
    if board == 'esp32_clock':
        from harden_ble import harden
        harden()
        flags = ['--build-property', 'compiler.c.extra_flags=-DMYNEWT_VAL_BLE_SM_SC_ONLY=1',
                 '--build-property', 'compiler.cpp.extra_flags=-DMYNEWT_VAL_BLE_SM_SC_ONLY=1']
    run([cli(), 'compile', '--fqbn', BOARDS[board], '--warnings', 'all', *flags,
         '--libraries', ROOT / 'shared', '--build-path', build_path,
         ROOT / 'firmware' / board], ROOT / 'docs' / (board + '-build.txt'))
    # Copy after arduino-cli exits. Its --output-dir hook can fail on Windows
    # while the linker still has the previous exported image memory-mapped.
    image_names = [f'{board}.ino.{suffix}' for suffix in
                   ('bin', 'bootloader.bin', 'partitions.bin', 'elf', 'merged.bin')]
    files = {}
    for name in image_names:
        source = build_path / name
        shutil.copy2(source, out / name)
        files[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    tracked_build = ROOT / 'firmware' / board / 'build' / 'esp32.esp32.esp32cam'
    if tracked_build.is_dir():
        for name in [*image_names, f'{board}.ino.map', 'build.options.json',
                     'partitions.csv', 'sdkconfig']:
            shutil.copy2(build_path / name, tracked_build / name)
    (out / 'manifest.json').write_text(json.dumps({'firmware': '0.4.7', 'protocol': 1,
        'fqbn': BOARDS[board], 'sha256': files}, indent=2) + '\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'build', 'test', 'ports', 'upload', 'monitor'])
    parser.add_argument('--board', choices=list(BOARDS))
    parser.add_argument('--port')
    parser.add_argument('--skip-build', action='store_true', help='upload the existing dist output')
    args = parser.parse_args()
    shorten_windows_paths()
    if args.action == 'setup':
        setup()
    elif args.action == 'build':
        for board in ([args.board] if args.board else BOARDS):
            build(board)
    elif args.action == 'test':
        run([sys.executable, ROOT / 'tests' / 'run.py'])
    elif args.action == 'ports':
        run([cli(), 'board', 'list'])
    else:
        if not args.board or not args.port:
            parser.error('--board and --port are required')
        if args.action == 'upload':
            if not args.skip_build:
                build(args.board)
            print('Motor power OFF. Check docs/wiring.md mode table before upload.', flush=True)
            run([cli(), 'upload', '--fqbn', BOARDS[args.board], '--port', args.port,
                 '--input-dir', ROOT / 'dist' / args.board, '--verify',
                 '--upload-property', 'upload.speed=115200', ROOT / 'firmware' / args.board],
                ROOT / 'docs/hardware' / (args.board + '-upload.txt'))
        else:
            run([cli(), 'monitor', '--port', args.port, '--config', 'baudrate=115200',
                 '--config', 'dtr=off', '--config', 'rts=off'], interactive=True)

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    from process_lifetime import configure_process_lifetime
    _job = configure_process_lifetime()
    main()
