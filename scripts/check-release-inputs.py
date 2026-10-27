#!/usr/bin/env python3
"""Fail publication on sensitive paths or private network references; print locations only."""
import argparse
from pathlib import PurePosixPath
import re
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--history', action='store_true', help='Check every commit reachable from --ref')
parser.add_argument('--ref', default='HEAD', help='Public release tip to inspect; excludes unrelated local refs')
args = parser.parse_args()
patterns = [
    ('private-network-name', re.compile(rb'\b[a-zA-Z0-9][a-zA-Z0-9.-]+\.ts\.net\b')),
    ('private-key', re.compile(rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----')),
    ('github-token', re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{40,})\b')),
]
forbidden_roots = {'data', 'ssh', 'sources', 'secrets', 'artifacts', 'preview', '.local'}
forbidden_suffixes = {'.pem', '.key', '.p12', '.pfx', '.jks', '.keystore'}
seen = set()
failures = []
refs = subprocess.check_output(['git', 'rev-list', args.ref], text=True).splitlines() if args.history else [subprocess.check_output(['git', 'write-tree'], text=True).strip()]
for ref in refs:
    for entry in subprocess.check_output(['git', 'ls-tree', '-rz', ref]).split(b'\0'):
        if not entry:
            continue
        metadata, raw_name = entry.split(b'\t', 1)
        mode, kind, object_id = metadata.decode().split()
        name = raw_name.decode('utf-8')
        path = PurePosixPath(name)
        if (path.parts[0] in forbidden_roots or path.suffix in forbidden_suffixes
                or (path.name.startswith('.env') and path.name != '.env.example')
                or name.startswith('docs/validation/') or name.startswith('docs/VALIDATION-LOCAL-')):
            failures.append((ref[:12], name, 'sensitive-path'))
        if mode in {'120000', '160000'}:
            failures.append((ref[:12], name, 'unreviewed-link-or-submodule'))
        if object_id in seen or kind != 'blob':
            continue
        seen.add(object_id)
        blob = subprocess.check_output(['git', 'cat-file', 'blob', object_id])
        for label, pattern in patterns:
            if pattern.search(blob):
                failures.append((ref[:12], name, label))
if failures:
    for ref, path, label in failures:
        print(f'{ref} {path}: {label}')
    sys.exit(1)
print(f'Publication input checks passed: {len(refs)} trees, {len(seen)} unique blobs. Run secret scanning and human review as well.')
