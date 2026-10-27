#!/usr/bin/env python3
"""Verify provenance and legacy configurations remain covered by image scanning."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('gitleaks', help='Path to the verified Gitleaks executable')
args = parser.parse_args()
repository = Path(__file__).resolve().parent.parent
members = {}


def blob(data, media_type):
    digest = hashlib.sha256(data).hexdigest()
    members['blobs/sha256/' + digest] = data
    return {'digest': 'sha256:' + digest, 'size': len(data), 'mediaType': media_type}


def encoded(value):
    return json.dumps(value).encode()


config = blob(encoded({'architecture': 'amd64', 'os': 'linux', 'config': {'Env': []}}), 'application/vnd.oci.image.config.v1+json')
layer_data = io.BytesIO()
with tarfile.open(fileobj=layer_data, mode='w') as layer:
    info = tarfile.TarInfo('app/message.txt')
    info.size = len(b'fixture')
    layer.addfile(info, io.BytesIO(b'fixture'))
layer = blob(layer_data.getvalue(), 'application/vnd.oci.image.layer.v1.tar')
image_manifest = blob(encoded({'schemaVersion': 2, 'config': config, 'layers': [layer]}), 'application/vnd.oci.image.manifest.v1+json')
# This deliberately altered public fingerprint is a detector fixture, not a credential.
public_fingerprint = '7169605F62C751356D054A26A821E680E5FA6305'
fixture_value = public_fingerprint[:-1] + '6'
provenance = blob(encoded({'_type': 'https://in-toto.io/Statement/v1', 'predicate': {'env': ['GPG_KEY=' + public_fingerprint]}}), 'application/vnd.in-toto+json')
attestation_manifest = blob(encoded({'schemaVersion': 2, 'config': config, 'layers': [provenance]}), 'application/vnd.oci.image.manifest.v1+json')
members['index.json'] = encoded({'schemaVersion': 2, 'manifests': [image_manifest, attestation_manifest]})
members['oci-layout'] = encoded({'imageLayoutVersion': '1.0.0'})
config_path = 'blobs/sha256/' + config['digest'].split(':')[1]
layer_path = 'blobs/sha256/' + layer['digest'].split(':')[1]
provenance_path = 'blobs/sha256/' + provenance['digest'].split(':')[1]
members['manifest.json'] = encoded([{'Config': config_path, 'RepoTags': ['fixture:review'], 'Layers': [layer_path]}])
legacy_paths = []
for values in ([public_fingerprint], [fixture_value], [public_fingerprint, fixture_value]):
    legacy = encoded({'id': '1' * 64, 'created': '2026-01-01T00:00:00Z', 'container_config': {}, 'architecture': 'amd64', 'os': 'linux', 'config': {'Env': ['GPG_KEY=' + value for value in values]}})
    descriptor = blob(legacy, 'application/json')
    legacy_paths.append('blobs/sha256/' + descriptor['digest'].split(':')[1])
# A config-shaped payload with an invalid content-address identity stays unclassified.
invalid_path = 'blobs/sha256/' + '0' * 64
members[invalid_path] = members[legacy_paths[0]]

with tempfile.TemporaryDirectory(prefix='unified-image-audit-') as directory:
    root = Path(directory)
    archive = root / 'image.tar'
    with tarfile.open(archive, 'w') as output:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            output.addfile(info, io.BytesIO(data))
    expanded = root / 'expanded'
    subprocess.run([sys.executable, str(repository / 'scripts/expand-image-for-audit.py'), str(archive), str(expanded)], check=True)
    assert (expanded / 'archive-metadata' / provenance_path).read_bytes() == members[provenance_path]
    assert (expanded / 'config-0.json').read_bytes() == members[config_path]
    assert (expanded / 'image-0-layer-0/app/message.txt').read_bytes() == b'fixture'
    mapping = {item['source']: item['output'] for item in json.loads((expanded / 'legacy-configs.json').read_text())}
    assert set(mapping) == set(legacy_paths)
    for path in legacy_paths:
        assert (expanded / mapping[path]).read_bytes() == members[path]
    assert (expanded / 'archive-metadata' / invalid_path).read_bytes() == members[invalid_path]
    report = root / 'findings.json'
    result = subprocess.run(
        [args.gitleaks, 'dir', str(expanded), '--config', str(repository / '.gitleaks.toml'), '--redact=100', '--no-banner', '--report-format', 'json', '--report-path', str(report)],
        text=True, capture_output=True, timeout=30,
    )
    if result.returncode != 1:
        raise SystemExit(f'Expected a provenance finding, received exit {result.returncode}')
    findings = json.loads(report.read_text())
    assert any(item['File'].endswith(provenance_path) and item['RuleID'] == 'generic-api-key' for item in findings)
    found = {Path(item['File']).name for item in findings}
    assert mapping[legacy_paths[0]] not in found
    assert mapping[legacy_paths[1]] in found and mapping[legacy_paths[2]] in found
    assert '0' * 64 in found
    print('Provenance detected; verified legacy configs retain bytes and detect changed/mixed values; invalid identity stays scanned.')
