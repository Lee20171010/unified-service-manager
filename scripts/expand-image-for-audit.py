#!/usr/bin/env python3
"""Expose all Docker filesystem layers, OCI metadata and provenance for inspection."""
import argparse
import json
from pathlib import Path, PurePosixPath
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


with tarfile.open(args.archive, 'r:*') as archive:
    manifests = json.load(archive.extractfile('manifest.json'))
    (output / 'manifest.json').write_text(json.dumps(manifests))
    layers = {name for manifest in manifests for name in manifest['Layers']}
    configs = {manifest['Config'] for manifest in manifests}
    # Preserve OCI index/manifests, attestations and any other archive payload.
    # Actual image configurations are copied below as config-N.json; filesystem
    # layer tarballs are expanded separately so deleted files are still scanned.
    archive_metadata = []
    for member in archive.getmembers():
        archive_metadata.append(metadata(member))
        path = safe_path(member.name)
        if member.isfile() and member.name not in layers | configs | {'manifest.json'}:
            target = output / 'archive-metadata' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open('wb') as destination:
                shutil.copyfileobj(source, destination)
    (output / 'archive-members.json').write_text(json.dumps(archive_metadata))
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
