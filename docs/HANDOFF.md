# Handoff · Unified 0.4

Read `README.md`, `RUNTIME-0.3.md`, `ARCHITECTURE.md`, `API.md`, `PARITY.md`, and `VALIDATION-0.3.md` before changes.

## Current implementation

Application/Web are 0.5.0; Android is 0.5.1 (versionCode 16). The selected circular-node U brand is retained. Docker releases are `ghcr.io/lee20171010/unified-application:0.5.0` and `ghcr.io/lee20171010/unified-web:0.5.0`; numeric tags are immutable and latest tracks the reviewed stable release. Packaging exports already built releases. OMV Compose contains only application and web with relative data/ssh/sources mounts.

`backend/docker-entrypoint.sh` starts with root to prepare empty root-owned DATA_DIR/SOURCE_DIR directories through storage_init, then execs the server via the Alpine setpriv package as 10001:10001 with no supplementary groups, zero capability sets and no-new-privileges. SSH remains read-only and its files/permissions are untouched. Docker's default startup capabilities are required; an explicit non-root Docker user skips initialization and needs prepared writable mounts. docker exec defaults to the image's root user; actual server identity must be checked on the running process. See OMV-COMPOSE.md and RELEASE-REVIEW-0.4.3.md. Existing operators should retain their previous images and matching Compose for rollback. Existing deployments retain their mount paths and project identity. Plugin authoring requires Application 0.4.0 or newer; supported plugin changes need no rebuild.

0.4.2 uses one compact server-name entry in both clients. It opens server/address details, with a separate Edit connection action before token fields. Routine screens show no architecture-layer status wording; demo and transient/authentication failures remain explicit. The Web uses its current origin, Android its saved URL, and the 0.4.1 auto-connect behavior is preserved. Reference research and checks are in [VALIDATION-0.4.2.md](VALIDATION-0.4.2.md).

0.4.1 corrects connection restoration: MainViewModel.observe bootstraps saved credentials within STARTED lifecycle, keeps snapshot/console while offline and retries read-only requests. Authentication errors stop retries until settings change. Credentials distinguishes stored connection from first-run demo form defaults. Web retains successfully validated credentials per origin and restores on startup/foreground/network recovery. Tests and limits are in [VALIDATION-0.4.1.md](VALIDATION-0.4.1.md).

Plugin pages in both clients create command plugins with custom fields, import JSON via file/paste, preview server validation and export clean JSON. Imports persist in the existing `/data/plugins/catalog/<id>/plugin.json` and take precedence over supplied catalog entries. Installation remains explicit. Read [PLUGIN-AUTHORING.md](PLUGIN-AUTHORING.md) for the developer workflow and [VALIDATION-0.4.0.md](VALIDATION-0.4.0.md) for evidence. Backend document operations are in Application/Plugins; Web UI is `plugin-editor.js`, native UI is `PluginEditor.kt` with requests through MainViewModel. No storage permission is needed for Android's system document picker.

Application owns use cases, validation, installed capability selection, job locks, worker execution and observations. Plugin installation is explicit and persisted centrally. Web and native Android share all resource/plugin/binding/job APIs. Three generic packages ship in the image; eight specific packages are discovered from the GitHub metadata index. No plugin is automatically installed.

The production sources are `backend/`, `web/`, `android/`, and `plugins/`. Preserve `prototype/` and `prototype/next/` as independent UI references. Artifacts contains distributable APKs, deployment/image bundles and checksums. `deploy/omv/compose.yaml` and `env.example` provide the manual OMV configuration; see `OMV-COMPOSE.md`.

- `plugins.py`: metadata discovery, immutable installed manifests, checksum, installation state, lifecycle.
- `resources.py`: reusable command/npm adapters, validation, quoting, fixed-version commands, observations.
- `application.py`: resource/binding use cases, active-target locking, plugin activation, worker.
- `job_sessions.py`: central PTY input, generations/sequences, transient post-job diagnostic shell.
- `store.py`: schema v1 JSON persistence, transactional multi-target lock checks and restart recovery.
- `backups.py`: common bounded archive/checksum/restore policy; unchanged application/storage hooks.
- Android Models/Forms/OverviewScreen consume descriptors; MainViewModel owns requests and session input state. Credentials remain in Keystore. Web credentials persist per origin in localStorage after successful verification, with session/memory fallback.

## Run and verify

Android 0.4.4 adds local diagnostics under Server → Diagnostic logs, including connection phases, safe exception code frames, JVM uncaught crashes and the prior Android process-exit reason (API 30+). Logs are bounded to 200 events / 64 KiB under noBackupFilesDir; export/share/clear require no server connection. Tokens, URLs, exception messages, response bodies, commands and stack filenames are excluded. The handler preserves Android's original uncaught-exception handling. See `ANDROID-DIAGNOSTICS.md` for the reproduction/export workflow and its limits. The diagnostics feature needs no additional API endpoints.

The user reports the connection switch works on Android 0.4.4 and failed on 0.4.2. The original crash cause is unconfirmed; diagnostic export remains available for future reproduction. Android 0.4.4 passes 42 JVM tests and the Android 16 emulator checks for connection failure/recovery, diagnostic preview, and a system-induced crash followed by export preview in a new process. The physical phone and final system document-picker save remain user acceptance checks. `ConnectionRouteTest`, `DiagnosticsTest` and `DiagnosticsScreenTest` cover local behavior. `scripts/test-android-device.sh` uses isolated packages, synthetic connections and an Android-induced crash/restart to test persistence; operator runtime details and exact current device results stay in ignored local reports. Read `TESTING.md` before running it.

For real-host acceptance, use `scripts/verify-local.py` only with an explicitly authorized private target plan. Keep host-specific outcomes outside the public repository. Current release fixture evidence is in [RELEASE-REVIEW-0.4.5.md](RELEASE-REVIEW-0.4.5.md); device and production-host acceptance remain separate.

Run `bash scripts/test.sh`, then `android/gradlew -p android :app:assembleDebug :app:testDebugUnitTest --max-workers=2`. Export OpenAPI using `scripts/export-api.sh`. Package the APK with `scripts/package-android.sh`. See `TESTING.md` for fixtures and device tests.

Before deployment back up SQLite with its online backup API and retain previous images. 0.3 keeps schema v1 and old service IDs, but rollback to 0.2 requires the pre-upgrade database because old clients cannot manage new resource kinds. No plugin is auto-installed during migration. Full runtime and package-authoring rules are in `RUNTIME-0.3.md`.

## Deployment ownership

Public source and versioned images are published under the project GitHub repository. Local review addresses, credentials, device details and real-host acceptance records stay outside the repository. Never operate on real hosts without an explicitly authorized target. Demo mode cannot contact SSH/WebDAV, and database mode identity separates demo from real execution.

## Follow-up boundaries

- Public distribution gate: review each commit before creation and every commit/content being pushed to GitHub, plus Docker build inputs and all image layers/history/metadata before image publication. Public release review evidence is recorded in SECURITY.md and the release review notes. The user's publication privacy requirement is recorded in AGENTS.md. Backup/migration feature work is deferred during ongoing development.
- npm user-prefix/project scope is implemented; automatic adoption of host-managed package caches is not.
- Dedicated billion-context/auth integrations declare package identity and host compatibility; administrators save application-version-specific register/unregister/probe recipes. OAuth accounts are not managed here.
- Host loaded versions are unknown until explicitly observed. No automatic restart or retry.
- Job Console opens a new diagnostic shell on the same connection after the managed program exits; preserving the original shell process/cwd is a further terminal improvement.
- Command/npm interface v1 is implemented. Arbitrary central executable plugins, dependency installers and archive distribution are not.
- Native physical-device acceptance, actual nas-host path/permission validation, backup-native export interoperability and production APK signing remain separate deployment tasks.

## Plugin defaults · 0.4.5

Release 0.4.5 adds four v1.1.0 Linux/systemd service recipes, renames billion-context (same ID, v1.1.0), and moves generic service/tool examples to examples/plugin-authoring. Exact original factory templates are hidden from discovery even in an existing catalog volume; installed or UI-imported copies remain usable. Nonempty per-instance commands take precedence. Newly introduced fields use manifest defaults, including when editing old resources. Both clients collapse optional command overrides. Android build 0.4.5 (code 13) contains this form change. Publication is performed by the reviewed release workflow; NAS updates remain an administrator action.

Read PLUGIN-CATALOG.md for prerequisites and manual JSON import/Update on persistent catalogs. Source lives in plugin-sources/linux-service.py; regenerate using scripts/build-plugin-catalog.py and check consistency with --check. Core/API schema remains v1. Run fixture tests before changing recipes; systemd/nvm/APT and upstream installers need authorized host-specific acceptance.

Plugin change validation: 96 backend fixture tests, 15 Web tests and 44 Android JVM tests passed; Android 0.4.5 debug APK built. Source credential scanning found no leaks. Service recipes were executed only against isolated fake executables; no user service was upgraded/restarted. The new native form tests use the documented 320dp Robolectric dialog workaround. No new device or production-host acceptance is claimed. The catalog archive contains 11 independent JSON packages plus usage notes; extract and import individual JSON files after the compatible core release. The exact reviewed commit and registry image digests are recorded in the publication workflow and GitHub release assets.

Release maintenance: backend/unified/__init__.py is the release version source; scripts/release-version.py reads it without runtime imports. OMV Compose uses IMAGE_TAG (latest by default). Container fixtures override it with the local candidate version and --pull never. Public-history scans use the reviewed commit ancestry, excluding unrelated local refs; push only refs/heads/main and the explicit reviewed release tag. See RELEASE-REVIEW-0.4.5.md for release gates.

The 0.4.5 security review also closed a legacy /services job-submission race: Application.submit holds the plugin lifecycle RLock while binding settings/versions and creating the durable job. submit_resource can safely nest via the RLock. The deterministic test synchronizes the competing operations and checks the worker's executed version.

## Android TLS cleanup · 0.4.6

A 0.4.5 diagnostic report showed HTTP 502 followed by NetworkOnMainThreadException during pooled TLS socket eviction. The interruption occurred during a container update and the endpoint later recovered. Api.close now schedules cancellation/eviction on its owned OkHttp dispatcher executor, independently of cancelled UI coroutine scopes. Closing is idempotent and new HTTP/WebSocket requests are rejected after closure. HTTPS validation and certificate verification remain unchanged.

ApiCloseTest uses real loopback HTTPS and records socket-close threads for 502 and successful responses; both cases fail before the fix. MainViewModelTest checks automatic 502 recovery without credential loss. HttpsRecoveryDeviceTest exercises actual AppRoute/Keystore/transport on the isolated emulator package with main-thread detectNetwork/penaltyDeathOnNetwork, including ViewModel cleanup after recovery. MockWebServer and fixture trust roots exist only in test dependencies. Server/Web/GHCR versions remain 0.4.5.

## GitHub plugin catalog · 0.5.0

Read PLUGIN-CATALOG.md for the current source and migration contract. plugin_catalog.py fetches only the fixed official GitHub origin; no administrator credentials are forwarded. A single lifecycle-owned metadata task starts after the worker lock and refreshes every six hours, with shutdown waiting for bounded in-flight work. Both clients can refresh explicitly. The validated metadata cache is atomic and survives refresh failure; package bytes are fetched on explicit actions and pinned by SHA-256. Installed packages remain the registry authority.

plugins/ holds authoring sources, catalog/index.json and catalog/packages hold published metadata/content-addressed packages, and the image copies only Compose/npm/WebDAV into /builtin-plugins. factory-plugin-hashes.json identifies exact historical shipped definitions in old volumes; modified legacy definitions copy into /data/plugins/catalog without overriding UI imports. Legacy volume originals remain for rollback. New package versions require regenerated catalog files, review and GitHub publication, not an Application image rebuild. Keep old published package files immutable.

## Android adaptive layout · 0.5.1

AdaptiveWorkspace uses Navigation 3 ListDetailSceneStrategy and the actual available width for host/resource details. NavigationSuiteScaffold chooses bar/rail. Selected IDs, page, filters and scroll state remain saveable. MainViewModel owns WorkspaceDrafts for form/connection/console inputs through configuration changes, without saving those drafts to disk. Successful workspace changes clear them. Closing an action form preserves the selected detail behind it. See ARCHITECTURE.md and TESTING.md for thresholds, ownership and acceptance boundaries.

Build with AGP 9.1.1 (built-in Kotlin), Kotlin Compose plugin 2.2.10, Gradle 9.3.1, JDK 17/21 and Android SDK 37.0. Adaptive 1.3.0 and Navigation 3 1.2.0 require this compile toolchain; minSdk 26 and targetSdk 35 are unchanged. Server/Web images and OMV Compose remain at 0.5.0.

Validation and native-only publication boundaries are in [RELEASE-REVIEW-ANDROID-0.5.1.md](RELEASE-REVIEW-ANDROID-0.5.1.md).
