# Application 0.4.2 · container startup validation

## Reference research and selected design

Reviewed upstream sources on 2026-10-27:

- [Redis Docker entrypoint](https://github.com/redis/docker-library-redis/blob/master/docker-entrypoint.sh): prepares storage when started as root, switches to the service user, and execs the program; permits explicit Docker user overrides.
- [PostgreSQL official image / Compose example](https://github.com/docker-library/docs/blob/master/postgres/README.md): the database service uses the image entrypoint for initialization, with deployment settings provided through environment and mounts.
- [PostgreSQL Docker entrypoint](https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh): prepares database directories before switching user and starting the server.
- [LinuxServer PUID/PGID](https://docs.linuxserver.io/general/understanding-puid-and-pgid/): an alternative configurable identity convention implemented by their images.
- [util-linux setpriv](https://github.com/util-linux/util-linux/blob/master/sys-utils/setpriv.1.adoc): UID/GID switching, supplementary groups, capability bounding/inheritable/ambient sets, exec and no-new-privileges.

Unified uses the root-preparation → non-root exec pattern with setpriv already present in its pinned Python base. No new OS package or supervisor is installed. Default UID/GID stays 10001 for compatibility with existing data. Explicit non-root Docker users skip preparation and supply their own writable mounts. PUID/PGID are not exposed.

The entrypoint initializes only empty root-owned DATA_DIR and SOURCE_DIR directory roots. Existing nonempty directories, other owners and child files retain permissions. SSH remains mounted read-only and is not initialized. The server runs with UID/GID 10001, no supplementary groups, all capability sets cleared and no-new-privileges. Docker exec/healthcheck still inherit the image's root configuration; main-process identity is verified separately.

## Checks

- Backend gate: **73 passed**. The seven focused storage initialization cases also passed.
- Web tests: 14 passed in `scripts/test.sh`; no client source changed.
- `scripts/test-entrypoint.py`: PASS for ordinary root startup dropping privileges, exact argument preservation, clean stdout, explicit non-root/read-only operation, and refusing to execute the program when directory preparation fails.
- `scripts/test-omv.py`: **PASS**. Uses a fresh temporary Compose project, random loopback port and no configured hosts. Checks two-service startup, data/source initialization, actual server UID/GID, all capability sets zero, no-new-privileges, read-only SSH, authentication, no activated plugins, imported document persistence across recreation, unchanged root-owned SSH fixture, and graceful stop.
- Signal diagnosis: Uvicorn logs `Application shutdown complete.` and `Finished server process`, then returns 143 by re-raising SIGTERM. Acceptance requires completed shutdown logs and exit 0 or 143, and rejects forced-kill exit 137.
- OpenAPI comparison with Application image 0.4.1: only the reported application version changes to 0.4.2; endpoint schemas are unchanged.

## Delivery and limits

Application is a new immutable image `unified-application:0.4.2`; Web and APK stay 0.4.2. Existing Application 0.4.1 and its distribution archives are retained for rollback. Exported artifacts include a backend-only update archive and a combined archive whose filename identifies both component versions.

Validation is local, using disposable fixture data and no remote operations. nas-host deployment and physical Android acceptance were not performed. Existing populated directories with incompatible permissions remain an administrator migration concern. Back up existing data and retain mount paths/project identity when replacing Compose; remove the prior storage-init service/dependency and cap_drop setting. See OMV-COMPOSE.md for copyable deployment steps.
