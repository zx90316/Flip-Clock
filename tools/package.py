"""Package only source, documentation and firmware; exclude local toolchains/caches/credentials."""
import hashlib
import json
import argparse
import os
from pathlib import Path
import zipfile
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT.parent / 'ESP32-CAM_翻頁時鐘_工程包.zip')
DEST = parser.parse_args().output.resolve()
SKIP = {'.tools', '.build', '.venv', '__pycache__', '.git'}
files = []
for folder, directories, names in os.walk(ROOT):
    directories[:] = [d for d in directories if d not in SKIP]
    files.extend(Path(folder) / name for name in names if not name.endswith('.pyc'))
hashes = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in files if p.name != 'SHA256SUMS.json'}
(ROOT / 'SHA256SUMS.json').write_text(json.dumps(hashes, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
files = [p for p in files if p.name != 'SHA256SUMS.json'] + [ROOT / 'SHA256SUMS.json']
with zipfile.ZipFile(DEST, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path in sorted(files):
        z.write(path, 'flip_clock/' + path.relative_to(ROOT).as_posix())
with zipfile.ZipFile(DEST) as z:
    bad = z.testzip()
    if bad:
        raise RuntimeError('ZIP verification failed: ' + bad)
print(DEST)
print('files:', len(files), 'bytes:', DEST.stat().st_size, 'sha256:', hashlib.sha256(DEST.read_bytes()).hexdigest())
