"""Fetch pinned test-only cJSON, verifying published source hashes."""
import hashlib
from pathlib import Path
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
HASHES = {'cJSON.c': '298581a04a36c0165da4b0aade235c23088cb2faa58651d720ea2f3706ed0b0d',
          'cJSON.h': '25b0145150d500498e4d209cec69c18c42cf818bffcc54690be3b895a2a16dee'}
def prepare():
    folder = ROOT / '.tools/cjson-1.7.19'
    folder.mkdir(parents=True, exist_ok=True)
    for name, digest in HASHES.items():
        path = folder / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            data = urllib.request.urlopen('https://raw.githubusercontent.com/DaveGamble/cJSON/v1.7.19/' + name, timeout=60).read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise RuntimeError('cJSON checksum mismatch')
            path.write_bytes(data)
        print(name, digest)
if __name__ == '__main__':
    prepare()
