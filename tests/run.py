"""Compile and execute the production C++ core and adapter simulations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.build/native'
BUILD.mkdir(parents=True, exist_ok=True)
ZIG = ROOT / '.tools/host/ziglang' / ('zig.exe' if os.name == 'nt' else 'zig')
env = os.environ.copy()
for key in ['TEMP', 'TMP', 'TMPDIR']:
    env[key] = str(BUILD)
env['ZIG_LOCAL_CACHE_DIR'] = str(BUILD / 'cache')
env['ZIG_GLOBAL_CACHE_DIR'] = str(BUILD / 'global-cache')
logs = []
def run(args):
    p = subprocess.run([str(x) for x in args], env=env, cwd=ROOT, capture_output=True, text=True)
    text = p.stdout + p.stderr
    logs.append(text)
    print(text, end='', flush=True)
    p.check_returncode()
flags = ['-std=c++17', '-Wall', '-Wextra', '-Werror', '-I' + str(ROOT / 'shared/protocol/src')]
binary = BUILD / ('core.exe' if os.name == 'nt' else 'core')
run([ZIG, 'c++', *flags, ROOT / 'tests/test_core.cpp', '-o', binary])
run([binary])
adapter = ROOT / 'tests/test_app.cpp'
if adapter.exists():
    dep = ROOT / '.tools/cjson-1.7.19'
    for name, digest in {'cJSON.c': '298581a04a36c0165da4b0aade235c23088cb2faa58651d720ea2f3706ed0b0d',
                         'cJSON.h': '25b0145150d500498e4d209cec69c18c42cf818bffcc54690be3b895a2a16dee'}.items():
        if hashlib.sha256((dep / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('cJSON checksum mismatch')
    obj = BUILD / 'cjson.o'
    run([ZIG, 'cc', '-std=c99', '-c', dep / 'cJSON.c', '-o', obj])
    binary = BUILD / ('app.exe' if os.name == 'nt' else 'app')
    run([ZIG, 'c++', *flags, '-I' + str(ROOT / 'tests/stubs'), '-I' + str(dep), adapter, obj, '-o', binary])
    run([binary])
run([sys.executable, '-m', 'unittest', 'discover', '-s', ROOT / 'tests', '-p', 'test_*.py'])
(ROOT / 'docs/host-tests.txt').write_text(''.join(logs), encoding='utf-8')
