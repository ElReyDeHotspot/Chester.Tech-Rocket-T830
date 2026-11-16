#!/usr/bin/env python3
"""Prepare locally signed GitHub Release assets. Never uploads or flashes."""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess

REPOSITORY = 'ElReyDeHotspot/Chester.Tech-Rocket-T830'
BOARD = 'mediatek,evb6990_cpe_mt76_emmc'


def prepare(image, key, output, version, sequence, boot_tested=False):
    image, key, output = map(pathlib.Path, (image, key, output))
    if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', version):
        raise ValueError('Version must have four numeric components, such as 2026.11.15.1')
    if sequence < 1:
        raise ValueError('Sequence must be positive and increase for every release')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*\.bin', image.name):
        raise ValueError('Unsafe firmware filename')
    if not 0 < image.stat().st_size <= 96 * 1024 * 1024:
        raise ValueError('Firmware must be between 1 byte and 96 MiB')
    with image.open('rb') as stream:
        magic = stream.read(2)
    if magic != b'\x1f\x8b':
        raise ValueError('Expected the vendor gzip sysupgrade format')
    output.mkdir(parents=True, exist_ok=True)
    dest = output / image.name
    if dest.resolve() != image.resolve():
        shutil.copyfile(image, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    manifest = {
        'schema': 1, 'repository': REPOSITORY,
        'hardware': {'board': BOARD, 'models': ['Misecte M620-N']},
        'release': {'version': version, 'sequence': sequence,
                    'status': 'stable' if boot_tested else 'candidate',
                    'boot_tested': bool(boot_tested)},
        'image': {'url': f'https://github.com/{REPOSITORY}/releases/download/v{version}/{dest.name}',
                  'filename': dest.name, 'size': dest.stat().st_size, 'sha256': digest},
    }
    data = output / 'ota.json'
    data.write_bytes((json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n').encode())
    subprocess.run(['openssl', 'pkeyutl', '-sign', '-rawin', '-inkey', str(key),
                    '-in', str(data), '-out', str(output / 'ota.json.sig')], check=True)
    (output / 'SHA256SUMS.txt').write_text(f'{digest}  {dest.name}\n', encoding='ascii')
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', required=True, type=pathlib.Path)
    p.add_argument('--private-key', required=True, type=pathlib.Path)
    p.add_argument('--output', required=True, type=pathlib.Path)
    p.add_argument('--version', required=True)
    p.add_argument('--sequence', required=True, type=int)
    p.add_argument('--boot-tested', action='store_true',
                   help='Attest that THIS EXACT BIN has passed hardware boot and recovery testing')
    a = p.parse_args()
    m = prepare(a.image, a.private_key, a.output, a.version, a.sequence, a.boot_tested)
    print(json.dumps(m, indent=2))
    print('Prepared locally only. Upload BIN, ota.json, ota.json.sig and SHA256SUMS.txt to the matching GitHub Release.')
    if not a.boot_tested:
        print('CANDIDATE: use a draft/prerelease. The OTA client rejects this manifest for installation.')


if __name__ == '__main__':
    main()
