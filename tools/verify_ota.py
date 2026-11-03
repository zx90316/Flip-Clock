"""Validate the freshly built OTA image and write its download checksum."""
import csv
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'dist' / 'esp32_clock'
IMAGE = OUTPUT / 'esp32_clock.ino.bin'
PARTITIONS = ROOT / 'firmware' / 'esp32_clock' / 'build' / 'esp32.esp32.esp32cam' / 'partitions.csv'


def verify():
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    manifest = json.loads((OUTPUT / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['firmware'] != version:
        raise RuntimeError(f"Build version {manifest['firmware']} does not match VERSION {version}")
    if manifest['fqbn'] != 'esp32:esp32:esp32cam:PartitionScheme=min_spiffs,FlashFreq=40':
        raise RuntimeError('Unexpected board or partition scheme')

    digest = hashlib.sha256(IMAGE.read_bytes()).hexdigest()
    if manifest['sha256']['esp32_clock.ino.bin'] != digest:
        raise RuntimeError('OTA image checksum differs from build manifest')

    with PARTITIONS.open(encoding='utf-8', newline='') as source:
        entries = {row[0].strip(): row for row in csv.reader(source)
                   if row and not row[0].lstrip().startswith('#')}
    slots = [int(entries[name][4].strip(), 0) for name in ('app0', 'app1')]
    if len(set(slots)) != 1 or IMAGE.stat().st_size > min(slots):
        raise RuntimeError('OTA image exceeds the app partition or partition sizes differ')

    (OUTPUT / 'SHA256SUMS.txt').write_text(f'{digest}  {IMAGE.name}\n', encoding='ascii')
    print(f'OTA v{version}: {IMAGE.stat().st_size} bytes / {slots[0]} byte slot; SHA-256 {digest}')
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write(f'version={version}\n')


if __name__ == '__main__':
    verify()
