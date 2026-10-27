# Deployment and operations

For **OMV Compose with prebuilt images**, use [OMV-COMPOSE.md](OMV-COMPOSE.md) and `deploy/omv/compose.yaml`. The amd64 offline bundle supplies Application/Web images. Paste Compose/env in OMV and set ADMIN_TOKEN; relative data directories are automatically created and initialized on first startup. Source-build instructions below remain available for development deployments.

## Local review

Demo mode uses isolated SQLite state and the intentionally public fixture token `unified-demo-token-local-only-2026`. Real mode rejects that token. Android starts with empty connection fields; operators enter their own HTTPS endpoint and token.

## Build and start a separate demo instance

Requirements: Docker Engine + Docker Compose, Python 3 for the configuration helper. No host Python dependencies are needed.

```bash
python3 scripts/configure.py
docker compose -f compose.yaml -f compose.demo.yaml up -d --build
```

Open http://127.0.0.1:4180 locally. For remote review:

```bash
tailscale serve --bg --https=9443 http://127.0.0.1:4180
```

Do not expose repository roots through a static server. Only Web build outputs, `prototype/`, or the dedicated `artifacts/` directory are suitable.

## Deploy real mode on nas-host

1. Place a checkout in an operator-selected directory, for example `/srv/unified`. Run `python3 scripts/configure.py`. The helper creates a private `.env` with a random administrator token and preserves existing configuration on later runs.
2. Keep `UNIFIED_MODE=ssh`. Choose a loopback `PORT`, and expose the Web service through Tailscale Serve or an existing HTTPS reverse proxy. Android requires valid HTTPS. Keep API internal to the Compose network.
3. Create a dedicated SSH account on each managed host. Grant only the intended operational access. Docker access is privileged; the operator chooses the permission model. Do not mount `/var/run/docker.sock` into this application.
4. Put the account's private key(s) and `known_hosts` inside `SSH_DIR`. Verify host-key fingerprints through an independent trusted channel before adding them; `ssh-keyscan` output alone is not verification. For non-default SSH ports, use `[hostname]:port` entries. The same hostname/IP used in the UI must match known_hosts.
5. The image entrypoint prepares writable storage and starts the application as UID/GID **10001**. SSH mounts remain read-only and are not modified. Keys must be readable by that UID and not world-readable. Example for a dedicated key directory: owner `10001:10001`, directory mode `0700`, key mode `0600`. Avoid changing ownership of unrelated user credentials.
6. Set `SOURCE_DIR` to a dedicated writable parent directory containing `magpie/` and `serverbox/`. These should contain configuration files intended for snapshots. Map actual application paths deliberately; v0.1 does not discover them. For container-hosted applications, arrange their configuration directories under this parent or use a deliberate staging workflow. Ownership and schema compatibility remain application-specific.
7. Configure `WEBDAV_URL` as an existing HTTPS collection and set `WEBDAV_USER` / `WEBDAV_PASSWORD` in `.env`. The account needs PUT and GET on that collection. Credentials must be separate from the URL. The application preserves existing remote files; archive names are unique. Redirects are not followed and certificate verification is enabled.
8. Start **without** the demo override:

```bash
docker compose -p unified-prod up -d --build
tailscale serve --bg --https=9443 http://127.0.0.1:4180
```

9. Open Web or Android and enter the generated token from `.env` over HTTPS. Add each host and its Compose project directories, then run **重新整理狀態** before a mutating operation. In real mode initial inventory is empty.

Use a different project name and port if demo and real instances coexist. Database mode identity prevents accidental reuse of demo state for real execution. Do not modify that marker to convert a database.

## Update and rollback

Before changing versions, stop accepting work, allow running jobs to finish, and save the current image IDs and application data. `docker compose down` preserves named volumes; **do not use `down -v`** during upgrades.

```bash
docker compose -p unified-prod stop
docker compose -p unified-prod build
docker compose -p unified-prod up -d
docker compose -p unified-prod ps
```

Schema v1 refuses incompatible schema versions. To roll back, use the saved images and a matching database backup. Do not start an old binary against a migrated database unless that migration explicitly supports it.

## Back up the manager itself

The WebDAV feature backs up application configuration snapshots; it does not back up Unified's own inventory, catalog, tokens, or SSH keys. Save these separately:

- `application-data` named volume: SQLite database, WAL, metadata, catalog and logs.
- `.env`: admin token and WebDAV settings, kept private.
- `SSH_DIR`: keys and verified known_hosts, kept private.
- `SOURCE_DIR`: current settings and `.unified-previous-*` rollback directories.

For a simple consistent manager backup, stop `application`, archive the entire named volume with an operator-approved destination, then restart it. An online backup must use SQLite's backup API rather than copying only the main `.sqlite3` file. Keep the backup catalog with the remote WebDAV archives: v0.1 does not rediscover orphaned archives automatically.

## Restore an application configuration

Quiesce the application that writes the source directory first. Select a known snapshot in either client, verify the application name, then confirm restore. Unified verifies the SHA-256 and archive format, installs staged files, and keeps the previous directory as `.unified-previous-<id>` beside the target. Inspect job output for its path. Restart or reload the consuming application as appropriate for that application.

If the host loses power during directory replacement, inspect the target and sibling previous/staging directories before starting the consumer. Restore the previous directory manually if required. After a successful verification, the operator may archive or remove old rollback directories. Version 0.1 intentionally has no automated retention policy.

## Android build

JDK 17 or 21, Android SDK 35, accepted SDK licenses. Gradle wrapper is pinned to 8.11.1 with checksum; AGP 8.7.3 and Kotlin 2.1.0 are pinned.

```bash
cd android
./gradlew :app:assembleDebug :app:testDebugUnitTest --max-workers=2
```

Set `ANDROID_HOME` or an untracked `android/local.properties` pointing to the local SDK. Result: `android/app/build/outputs/apk/debug/app-debug.apk`.

`scripts/package-android.sh` copies the debug-signed review APK to `artifacts/` with a SHA-256 checksum. A distributable production release requires a maintained signing key and a release signing configuration; never commit that key or password. The current APK is for review and manual installation, not a Play Store release.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| 401 | Token matches this server; demo token is rejected in real mode |
| 409 | Another job for the target is queued/running, or inventory name already exists |
| SSH_CONFIG_MISSING | UID 10001 can read selected key and known_hosts |
| HostKeyNotVerifiable | Address/port and trusted fingerprint match; verify before updating |
| Compose fails | Host account can execute Docker Compose and access the registered directory |
| Unknown service state | Run refresh; read failed job before retrying a mutation |
| WebDAV HTTPStatusError | Collection exists, account permissions, server logs and TLS certificate |
| Restore rename error | Mount the writable parent, not the individual application directory |
| Android cannot connect | Tailscale connected, valid HTTPS certificate, correct origin/token |
| App restart during job | Job is marked uncertain; inspect host state before retrying |

Read container logs with `docker compose logs --tail=100 application web`. Do not paste credentials or sensitive command output into public issues.

## 0.3 plugin/resource upgrade

Read [RUNTIME-0.3.md](RUNTIME-0.3.md). Back up SQLite with its backup API and retain old images before rollout. Build the Application/Web containers once and install APK 0.3.0. The catalog is mounted read-only from `${PLUGIN_CATALOG:-./plugins}`; installed checksummed manifests and activation state live in the data volume. New installations and migrated databases have no active plugins until Install is selected.

Subsequent supported command/npm plugin updates use a new manifest version and the Plugin page; no image rebuild is needed. Restore the pre-upgrade database plus old images for rollback to 0.2. Keep real and demo volumes separate.
