#!/usr/bin/env python3
"""Expose all Docker filesystem layers, OCI metadata and provenance for inspection."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile

parser = argparse.ArgumentParser()
parser.add_argument('archive')
parser.add_argument('output')
args = parser.parse_args()
output = Path(args.output)
output.mkdir(parents=True, exist_ok=False)
count = 0


def safe_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe archive path')
    return path


def metadata(member):
    return {
        key: getattr(member, key)
        for key in ('name', 'linkname', 'size', 'mode', 'uid', 'gid', 'uname', 'gname', 'mtime', 'pax_headers')
    } | {'type': member.type.decode('latin-1')}


def is_legacy_config(name, data):
    """Recognize Moby V1 compatibility configs without treating arbitrary JSON as config."""
    digest = re.fullmatch(r'blobs/sha256/([0-9a-f]{64})', name)
    if not digest or hashlib.sha256(data).hexdigest() != digest[1]:
        return False
    try:
        value = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return False
    if not isinstance(value, dict) or 'rootfs' in value or 'history' in value:
        return False
    config = value.get('config')
    return (
        isinstance(value.get('id'), str)
        and re.fullmatch(r'[0-9a-f]{64}', value['id']) is not None
        and isinstance(value.get('created'), str)
        and isinstance(value.get('container_config'), dict)
        and isinstance(value.get('architecture'), str)
        and value.get('os') in ('linux', 'windows')
        and isinstance(config, dict)
        and isinstance(config.get('Env'), list)
        and all(isinstance(item, str) for item in config['Env'])
    )


with tarfile.open(args.archive, 'r:*') as archive:
    manifests = json.load(archive.extractfile('manifest.json'))
    (output / 'manifest.json').write_text(json.dumps(manifests))
    layers = {name for manifest in manifests for name in manifest['Layers']}
    configs = {manifest['Config'] for manifest in manifests}
    # Preserve OCI index/manifests, attestations and any other archive payload.
    # Actual image configurations are copied below as config-N.json; filesystem
    # layer tarballs are expanded separately so deleted files are still scanned.
    archive_metadata = []
    legacy_configs = []
    for member in archive.getmembers():
        archive_metadata.append(metadata(member))
        path = safe_path(member.name)
        if member.isfile() and member.name not in layers | configs | {'manifest.json'}:
            if member.size <= 4 * 1024 * 1024:
                data = archive.extractfile(member).read()
                if is_legacy_config(member.name, data):
                    name = f'legacy-config-{len(legacy_configs)}.json'
                    (output / name).write_bytes(data)
                    legacy_configs.append({'source': member.name, 'output': name, 'sha256': hashlib.sha256(data).hexdigest()})
                    continue
            target = output / 'archive-metadata' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open('wb') as destination:
                shutil.copyfileobj(source, destination)
    (output / 'archive-members.json').write_text(json.dumps(archive_metadata))
    (output / 'legacy-configs.json').write_text(json.dumps(legacy_configs))
    for image, manifest in enumerate(manifests):
        (output / f'config-{image}.json').write_bytes(archive.extractfile(manifest['Config']).read())
        for number, name in enumerate(manifest['Layers']):
            root = output / f'image-{image}-layer-{number}'
            root.mkdir()
            with tarfile.open(fileobj=archive.extractfile(name), mode='r:*') as layer:
                members = []
                for member in layer:
                    path = safe_path(member.name)
                    members.append(metadata(member))
                    if member.isfile():
                        target = root.joinpath(*path.parts)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with layer.extractfile(member) as source, target.open('wb') as destination:
                            shutil.copyfileobj(source, destination)
                        count += 1
                (output / f'image-{image}-layer-{number}-members.json').write_text(json.dumps(members))
print(f'Expanded {count} regular files across all layers; OCI payloads and tar metadata retained; links not materialized.')
