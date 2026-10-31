"""Independent Python wire reference; regenerates committed frame vectors."""
import binascii
import json
from pathlib import Path
import struct
def frame(op, session, seq=0, args=(0, 0, 0, 0)):
    payload = struct.pack('<BBBBIIIIIIH', 0xA5, 1, op, 0, session, seq, *args, 0)
    assert len(payload) == 30
    return payload + struct.pack('<H', binascii.crc_hqx(payload, 0xFFFF))
if __name__ == '__main__':
    result = {'algorithm': 'CRC-16/CCITT-FALSE, LE CRC, 30-byte payload',
              'check_123456789': f'{binascii.crc_hqx(b"123456789", 0xFFFF):04X}',
              'vectors': [{'name': name, 'hex': frame(op, 42, seq, args).hex()} for name, op, seq, args in [
                  ('OPEN', 1, 0, (0, 0, 0, 0)), ('HEARTBEAT', 3, 0, (0, 0, 0, 0)),
                  ('ARM', 2, 1, (200, 120000, 0, 0)), ('MOVE_136', 16, 2, (136, 200, 100, 20000)),
                  ('STOP', 17, 3, (0, 0, 0, 0)), ('DISARM', 18, 4, (0, 0, 0, 0))]]}
    Path(__file__).with_name('vectors.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
