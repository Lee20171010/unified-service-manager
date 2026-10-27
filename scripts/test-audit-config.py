#!/usr/bin/env python3
"""Verify a public-fingerprint exception cannot hide other image/source findings."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('gitleaks', help='Path to the verified Gitleaks executable')
args = parser.parse_args()
config = Path(__file__).resolve().parent.parent / '.gitleaks.toml'
public_fingerprint = '7169605F62C751356D054A26A821E680E5FA6305'
different_fingerprint = public_fingerprint[:-1] + '6'

with tempfile.TemporaryDirectory(prefix='unified-audit-config-') as directory:
    for case, name, values, expected in (
        ('public-base', 'config-0.json', [public_fingerprint], 0),
        ('source', 'source.txt', [public_fingerprint], 1),
        ('different-key', 'config-1.json', [different_fingerprint], 1),
        ('mixed-config', 'config-2.json', [public_fingerprint, different_fingerprint], 1),
        ('legacy-public', 'legacy-config-0.json', [public_fingerprint], 0),
        ('legacy-different', 'legacy-config-1.json', [different_fingerprint], 1),
        ('legacy-mixed', 'legacy-config-2.json', [public_fingerprint, different_fingerprint], 1),
        ('unknown-provenance', 'provenance.json', [public_fingerprint], 1),
    ):
        root = Path(directory) / case
        root.mkdir()
        (root / name).write_text('[' + ','.join('"GPG_KEY=' + value + '"' for value in values) + ']')
        result = subprocess.run(
            [args.gitleaks, 'dir', str(root), '--config', str(config), '--redact=100', '--no-banner'],
            text=True, capture_output=True, timeout=30,
        )
        if result.returncode != expected:
            raise SystemExit(f'{case}: expected exit {expected}, received {result.returncode}')
        print(f'{case}: expected classification confirmed')
