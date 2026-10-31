"""Apply one auditable policy patch to pinned NimBLE 2.5.1: reject repeat pairing.

Re-pairing requires UART clear_bonds + pair. Upstream silently deletes an old bond.
"""
import hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = 'af4335cf6b9e5ca3be63770307736fe50d29b53529c0dd3579f7ed515b553895'
MARKER = '// FlipClock policy: bond replacement requires local clear_bonds.'
def harden():
    path = ROOT / '.tools/user/libraries/NimBLE-Arduino/src/NimBLEServer.cpp'
    data = path.read_bytes()
    if MARKER.encode() in data:
        # Verify all other source content against the original by restoring the recorded block.
        backup = path.with_suffix('.cpp.upstream')
        if not backup.exists() or hashlib.sha256(backup.read_bytes()).hexdigest() != ORIGINAL:
            raise RuntimeError('NimBLE upstream checksum mismatch')
        expected = patched(backup.read_bytes())
        if data != expected:
            raise RuntimeError('NimBLE policy patch checksum mismatch')
        return
    if hashlib.sha256(data).hexdigest() != ORIGINAL:
        raise RuntimeError('Expected unmodified NimBLE-Arduino 2.5.1')
    path.with_suffix('.cpp.upstream').write_bytes(data)
    path.write_bytes(patched(data))
def patched(data):
    begin = data.index(b'        case BLE_GAP_EVENT_REPEAT_PAIRING: {')
    end = data.index(b'        } // BLE_GAP_EVENT_REPEAT_PAIRING', begin) + len(b'        } // BLE_GAP_EVENT_REPEAT_PAIRING')
    return data[:begin] + (b'        case BLE_GAP_EVENT_REPEAT_PAIRING: {\n            ' + MARKER.encode() +
        b'\n            return BLE_GAP_REPEAT_PAIRING_IGNORE;\n        } // BLE_GAP_EVENT_REPEAT_PAIRING') + data[end:]
if __name__ == '__main__':
    harden()
