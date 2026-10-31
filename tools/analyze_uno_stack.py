"""Separate non-LTO analysis build; does not replace delivered firmware."""
import re
from pathlib import Path
import build
build.shorten_windows_paths()
folder = build.ROOT / '.build/uno-stack'
build.run([build.cli(), 'compile', '--fqbn', build.BOARDS['uno_motor'],
    '--libraries', build.ROOT / 'shared', '--build-path', folder,
    '--build-property', 'compiler.c.extra_flags=-fno-lto -fstack-usage',
    '--build-property', 'compiler.cpp.extra_flags=-fno-lto -fstack-usage',
    '--build-property', 'compiler.c.elf.extra_flags=-fno-lto -fstack-usage',
    build.ROOT / 'firmware/uno_motor'], build.ROOT / 'docs/uno-stack-build.txt')
rows = []
for path in folder.rglob('*.su'):
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        fields = line.split('\t')
        if len(fields) == 3 and fields[1].isdigit():
            rows.append({'function': fields[0].split(':', 3)[-1], 'bytes': int(fields[1]), 'kind': fields[2]})
rows.sort(key=lambda r: r['bytes'], reverse=True)
if not rows:
    raise RuntimeError('Compiler did not emit stack usage files')
text = '# Uno 堆疊預算與編譯分析\n\n'
text += '正式 LTO 韌體靜態 RAM 869 bytes，剩餘 1,179 bytes。下表來自另行 -fno-lto -fstack-usage 分析編譯，不替代正式映像，亦不是實機高水位量測。表中包含 Arduino 核心已編譯但未必鏈結進韌體的函式；出現 String 函式不表示本程式使用動態 String。\n\n'
text += '| 函式 | 單一 frame bytes | 編譯器分類 |\n|---|---:|---|\n'
for row in rows[:25]:
    text += f"| `{row['function']}` | {row['bytes']} | {row['kind']} |\n"
text += '\n工程預算：主迴圈及最深呼叫鏈保留 512 bytes，另為 TWI ISR、Wire callback、暫存器與返回位址保留 256 bytes，共 768 bytes；在 1,179-byte 空間中另留 411 bytes 裕量。程式無遞迴或動態配置，receive/request callback 只拷貝固定 32-byte 資料。\n\n'
text += '這是保守設計預算，未自動證明所有呼叫路徑的全域最壞值；LTO、ISR 巢狀條件與 bootloader 行為仍須實機以 stack canary／高水位量測及壓力測試驗證。不能把單一最大 frame 或剩餘 RAM 當成已驗證最壞堆疊。\n'
(build.ROOT / 'docs/uno-stack.md').write_text(text, encoding='utf-8')
print('Stack analysis functions:', len(rows), 'largest frame:', rows[0]['bytes'])
