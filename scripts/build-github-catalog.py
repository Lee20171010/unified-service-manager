#!/usr/bin/env python3
"""Build/check the official metadata index and content-addressed JSON packages."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BUILTIN_IDS = {'compose', 'npm-packages', 'webdav'}

def manifest_bytes(m):
    return (json.dumps(m, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()

parser = argparse.ArgumentParser()
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
entries = []
outputs = {}
for path in sorted((ROOT/'plugins').glob('*/*/plugin.json')):
    m = json.loads(path.read_text())
    if m['id'] in BUILTIN_IDS:
        continue
    raw = manifest_bytes(m)
    digest = hashlib.sha256(raw).hexdigest()
    outputs[ROOT/'catalog/packages'/m['id']/f'{m["version"]}-{digest}.json'] = raw
    entries.append(dict(id=m['id'], label=m['label'], version=m['version'], category=m['category'],
                        description=m.get('description',''), hosts=m.get('hosts',[]), sha256=digest))
index = dict(schema_version=1, plugins=entries)
outputs[ROOT/'catalog/index.json'] = (json.dumps(index, ensure_ascii=False, indent=2)+'\n').encode()
for path, raw in outputs.items():
    if args.check:
        if not path.exists() or path.read_bytes() != raw:
            raise SystemExit(f'Catalog differs: {path.relative_to(ROOT)}')
    else:
        if path.parent.name != 'catalog':
            for prior in path.parent.glob(path.name.rsplit('-', 1)[0]+'-*.json'):
                if prior != path:
                    raise SystemExit(f'Published package version is immutable: {path.parent.name}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
print(f'Official catalog: {len(entries)} packages verified' if args.check else f'Official catalog: {len(entries)} packages generated')
