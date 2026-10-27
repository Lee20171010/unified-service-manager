# Handoff · Unified 0.4

Read `README.md`, `RUNTIME-0.3.md`, `ARCHITECTURE.md`, `API.md`, `PARITY.md`, and `VALIDATION-0.3.md` before changes.

## Current implementation

Web, Android and Application are 0.4.3 (native versionCode 11). The selected circular-node U brand is retained. Docker releases are `ghcr.io/lee20171010/unified-application:0.4.3` and `ghcr.io/lee20171010/unified-web:0.4.3`; numeric tags are immutable. Packaging exports already built releases. OMV Compose contains only application and web with relative data/ssh/sources mounts.

`backend/docker-entrypoint.sh` starts with root to prepare empty root-owned DATA_DIR/SOURCE_DIR directories through storage_init, then execs the server via the Alpine setpriv package as 10001:10001 with no supplementary groups, zero capability sets and no-new-privileges. SSH remains read-only and its files/permissions are untouched. Docker's default startup capabilities are required; an explicit non-root Docker user skips initialization and needs prepared writable mounts. docker exec defaults to the image's root user; actual server identity must be checked on the running process. See OMV-COMPOSE.md and RELEASE-REVIEW-0.4.3.md. Existing operators should retain their previous images and matching Compose for rollback. Existing deployments retain their mount paths and project identity. Plugin authoring requires Application 0.4.0 or newer; supported plugin changes need no rebuild.

0.4.2 uses one compact server-name entry in both clients. It opens server/address details, with a separate Edit connection action before token fields. Routine screens show no architecture-layer status wording; demo and transient/authentication failures remain explicit. The Web uses its current origin, Android its saved URL, and the 0.4.1 auto-connect behavior is preserved. Reference research and checks are in [VALIDATION-0.4.2.md](VALIDATION-0.4.2.md).

0.4.1 corrects connection restoration: MainViewModel.observe bootstraps saved credentials within STARTED lifecycle, keeps snapshot/console while offline and retries read-only requests. Authentication errors stop retries until settings change. Credentials distinguishes stored connection from first-run demo form defaults. Web retains successfully validated credentials per origin and restores on startup/foreground/network recovery. Tests and limits are in [VALIDATION-0.4.1.md](VALIDATION-0.4.1.md).

Plugin pages in both clients create command plugins with custom fields, import JSON via file/paste, preview server validation and export clean JSON. Imports persist in the existing `/data/plugins/catalog/<id>/plugin.json` and take precedence over supplied catalog entries. Installation remains explicit. Read [PLUGIN-AUTHORING.md](PLUGIN-AUTHORING.md) for the developer workflow and [VALIDATION-0.4.0.md](VALIDATION-0.4.0.md) for evidence. Backend document operations are in Application/Plugins; Web UI is `plugin-editor.js`, native UI is `PluginEditor.kt` with requests through MainViewModel. No storage permission is needed for Android's system document picker.

Application owns use cases, validation, installed capability selection, job locks, worker execution and observations. Plugin installation is explicit and persisted centrally. Web and native Android share all resource/plugin/binding/job APIs. The 13 catalog folders are available packages, not automatically installed integrations.

The production sources are `backend/`, `web/`, `android/`, and `plugins/`. Preserve `prototype/` and `prototype/next/` as independent UI references. Artifacts contains distributable APKs, deployment/image bundles and checksums. `deploy/omv/compose.yaml` and `env.example` provide the manual OMV configuration; see `OMV-COMPOSE.md`.

- `plugins.py`: metadata discovery, immutable installed manifests, checksum, installation state, lifecycle.
- `resources.py`: reusable command/npm adapters, validation, quoting, fixed-version commands, observations.
- `application.py`: resource/binding use cases, active-target locking, plugin activation, worker.
- `job_sessions.py`: central PTY input, generations/sequences, transient post-job diagnostic shell.
- `store.py`: schema v1 JSON persistence, transactional multi-target lock checks and restart recovery.
- `backups.py`: common bounded archive/checksum/restore policy; unchanged application/storage hooks.
- Android Models/Forms/OverviewScreen consume descriptors; MainViewModel owns requests and session input state. Credentials remain in Keystore. Web credentials persist per origin in localStorage after successful verification, with session/memory fallback.

## Run and verify

For real-host acceptance, use `scripts/verify-local.py` only with an explicitly authorized private target plan. Keep host-specific outcomes outside the public repository. Current release fixture evidence is in [RELEASE-REVIEW-0.4.3.md](RELEASE-REVIEW-0.4.3.md); device and production-host acceptance remain separate.

Run `bash scripts/test.sh`, then `android/gradlew -p android :app:assembleDebug :app:testDebugUnitTest --max-workers=2`. Export OpenAPI using `scripts/export-api.sh`. Package the APK with `scripts/package-android.sh`. See `TESTING.md` for fixtures and device tests.

Before deployment back up SQLite with its online backup API and retain previous images. 0.3 keeps schema v1 and old service IDs, but rollback to 0.2 requires the pre-upgrade database because old clients cannot manage new resource kinds. No plugin is auto-installed during migration. Full runtime and package-authoring rules are in `RUNTIME-0.3.md`.

## Deployment ownership

Public source and versioned images are published under the project GitHub repository. Local review addresses, credentials, device details and real-host acceptance records stay outside the repository. Never operate on real hosts without an explicitly authorized target. Demo mode cannot contact SSH/WebDAV, and database mode identity separates demo from real execution.

## Follow-up boundaries

- Public distribution gate: review each commit before creation and every commit/content being pushed to GitHub, plus Docker build inputs and all image layers/history/metadata before image publication. Public release review evidence is recorded in SECURITY.md and the release review notes. The user's publication privacy requirement is recorded in AGENTS.md. Backup/migration feature work is deferred during ongoing development.
- npm user-prefix/project scope is implemented; automatic adoption of host-managed package caches is not.
- Dedicated bili/auth integrations declare package identity and host compatibility; administrators save application-version-specific register/unregister/probe recipes. OAuth accounts are not managed here.
- Host loaded versions are unknown until explicitly observed. No automatic restart or retry.
- Job Console opens a new diagnostic shell on the same connection after the managed program exits; preserving the original shell process/cwd is a further terminal improvement.
- Command/npm interface v1 is implemented. Arbitrary central executable plugins, dependency installers and archive distribution are not.
- Native physical-device acceptance, actual nas-host path/permission validation, backup-native export interoperability and production APK signing remain separate deployment tasks.
