#!/bin/sh
set -eu
umask 0077

if [ "$(id -u)" = 0 ]; then
    python -m unified.storage_init
    export HOME=/home/unified USER=unified LOGNAME=unified
    exec setpriv --reuid=10001 --regid=10001 --clear-groups \
        --bounding-set=-all --inh-caps=-all --ambient-caps=-all \
        --no-new-privs "$@"
fi

# An explicit non-root Docker user owns preparation of its mounted directories.
exec "$@"
