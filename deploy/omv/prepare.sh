#!/usr/bin/env bash
# Import images and prepare files; OMV Compose owns container creation/start.
set -euo pipefail
bundle_dir=$(cd -- "$(dirname -- "$0")" && pwd)
target_dir=${1:?Usage: sudo bash prepare.sh /absolute/dedicated/unified-directory}
if [[ "$target_dir" != /* || "$target_dir" == / || "$target_dir" =~ [^a-zA-Z0-9_./-] || "/$target_dir/" == *"/../"* ]]; then
  echo 'Use a dedicated absolute directory with letters, digits, _, -, / and . only.' >&2
  exit 1
fi
if [[ "$(uname -m)" != x86_64 ]]; then
  echo 'This image bundle requires x86_64 / amd64.' >&2
  exit 1
fi
cd "$bundle_dir"
sha256sum -c images.tar.gz.sha256
docker load -i images.tar.gz
mkdir -p -- "$target_dir"
target_dir=$(cd -- "$target_dir" && pwd)
if [[ "$target_dir" == / ]]; then
  echo 'The resolved target must be a dedicated directory, not /.' >&2
  exit 1
fi
docker run --rm -i --network none --read-only --user 0:0 \
  -e "USM_TARGET=$target_dir" \
  -v "$target_dir:/target" -v "$bundle_dir/compose.yaml:/release-compose.yaml:ro" \
  --entrypoint python unified-application:0.3.0-omv1 - <<'PY'
import os, secrets, shutil
from pathlib import Path
root = Path('/target')
for name in ('data', 'ssh', 'sources'):
    directory = root / name
    if not directory.exists():
        directory.mkdir(mode=0o700)
        os.chown(directory, 10001, 10001)
    elif not directory.is_dir():
        raise SystemExit(f'{name} must be a directory')
    elif directory.stat().st_uid != 10001:
        raise SystemExit(f'Existing {name} owner is not UID 10001. Existing contents were preserved; inspect permissions before proceeding.')
catalog = root / 'plugins'
if not catalog.exists():
    shutil.copytree('/plugin-catalog', catalog)
else:
    print('Existing plugin catalog preserved.')
env = root / 'omv.env'
if not env.exists():
    content = ('USM_ROOT=' + os.environ['USM_TARGET'] + '\n'
               'ADMIN_TOKEN=' + secrets.token_urlsafe(48) + '\n'
               'BIND_ADDRESS=127.0.0.1\nPORT=4180\n'
               'WEBDAV_URL=\nWEBDAV_USER=\nWEBDAV_PASSWORD=\n')
    fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)
else:
    print('Existing omv.env preserved.')
compose = root / 'omv-compose.yaml'
if not compose.exists():
    shutil.copyfile('/release-compose.yaml', compose)
else:
    print('Existing omv-compose.yaml preserved.')
print('Ready: omv-compose.yaml → OMV File; omv.env → OMV Environment. Save and select Up.')
print('No application containers were started. Administrator token was not printed.')
PY
