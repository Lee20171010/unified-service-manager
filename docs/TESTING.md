# Testing and acceptance

Tests use isolated state. They must not submit work to real NAS hosts or application directories.

## Backend and Web syntax

```bash
bash scripts/test.sh
```

The script builds the Application image and a separate test image, runs pytest, and checks both Web JavaScript modules. Python packages are pinned by `backend/requirements-lock.txt`.

- `test_application.py`: authenticated API, inventory, service actions, logs, conflicts, backup/restore, mode isolation and Terminal protocol.
- `test_adapters.py`: local SSH fixture with host-key verification, HTTP WebDAV fixture, archive integrity/path checks and cancellation of filesystem transactions.
- `test_lifecycle.py`: database transaction commit/rollback/close and uncertain service state after shutdown/restart. These regressions were reproduced before their fixes.

Tests create temporary databases, keys and application files. No production credential is required.

## Native Android

JDK 17/21 and Android SDK 35 are required. The first run downloads test libraries and Android runtime jars from their package repositories.

```bash
android/gradlew -p android :app:testDebugUnitTest --max-workers=1
android/gradlew -p android :app:assembleDebug --max-workers=1
```

- `ApiTest`: HTTPS connection URL validation.
- `MainViewModelTest`: virtual-time coroutine tests for failed connections, delayed responses, repeated submission, polling cancellation and console session isolation. `ApplicationClient` and `ConnectionStore` are small constructor-injected boundaries; production uses `Api` and Android Keystore-backed `Credentials`.
- `ScreenTest`: Compose semantics tests for managed service operations, restore confirmation, backup application selection, saved navigation, connection dialog behavior and Terminal input. Robolectric runs these locally with an API 28 runtime; there is no live server or physical device dependency.

The connection-dialog test uses a 320 dp window because of the upstream [Robolectric dialog measurement issue #8460](https://github.com/robolectric/robolectric/issues/8460). Other screen tests use 411 × 891 dp. The test-only qualifier avoids that runtime limitation; the product layout is unchanged. Wider dialog layout and keyboard behavior remain part of device acceptance.

Reports are generated under `android/app/build/reports/tests/testDebugUnitTest/`; XML evidence is under `android/app/build/test-results/testDebugUnitTest/`. Do not commit build output. A failed test must be resolved before replacing the downloadable APK.

Use `scripts/package-android.sh` to rerun tests, build and copy the APK/checksum into `artifacts/`. For low-memory review hosts, run a single Gradle worker and avoid running multiple builds together.

## Required real-device acceptance

Local Compose tests do not establish device rendering, Android Keystore behavior, system document picker integration or tailnet networking. On the intended device:

1. Connect through Tailscale to the review URL and test valid/invalid tokens.
2. Add a demo host/service, refresh, start/stop/restart/upgrade, and confirm the same results appear in Web.
3. Run a long demo job, background and restore the app, rotate the device, and reopen the same job. Check stdout/stderr and save the full log through the document picker.
4. Back up each supported application and restore the selected demo snapshot with confirmation.
5. Open Terminal from host and service details. Exercise input, Ctrl+C/Ctrl+D, closing and reopening, and the on-screen keyboard.
6. Disconnect/reconnect the network, then change the workspace connection. Ensure old data and output do not appear in the new workspace.

Record device model, OS version, APK hash, server version and outcomes in `VALIDATION.md`. Real SSH/WebDAV acceptance additionally requires the concrete targets listed in `DEPLOYMENT.md`.

## Framework references

- [Android Robolectric testing](https://developer.android.com/training/testing/local-tests/robolectric)
- [Compose testing](https://developer.android.com/develop/ui/compose/testing)
- [Robolectric setup](https://robolectric.org/getting-started/)

## Appearance regression checks

`scripts/test.sh` also runs `node --test tests/web-theme.test.cjs`. It evaluates the shipped early-load script with controlled OS/storage events: first paint, OS updates, all three persisted choices, cross-tab changes, invalid values and denied storage. Android `ThemeTest` checks persisted/default preferences and uses real Compose controls to verify palette changes, explicit overrides and live system updates.

For device acceptance, change Android system appearance while Unified is open in system mode, select each explicit mode, reopen the app, and inspect status/navigation bars, forms, Job Console and Terminal with the keyboard visible. Local JVM tests do not verify physical system bars.

## Adapter contract checks

`test_registry.py` registers a read-only fixture service, a new configuration backup application and in-memory storage, then uses authenticated API requests and the real job worker to prove execution and restore. It covers unsupported operations before enqueue, duplicate target identities, legacy records and request compatibility, missing adapters, interface/version validation, secret-free discovery, pre-mutation application validation and demo transport isolation. Existing SSH/WebDAV/archive/lifecycle tests continue to exercise the transport and common policy boundaries.

Web tests cover server-driven action subsets, new adapter/application discovery, incompatible interfaces, fail-closed missing capabilities and settings serialization. Native `AdapterTest` checks parsing, a read-only service's visible operations, dynamic field switching without stale settings and a newly registered backup choice through Compose semantics. The new form tests use the same documented 320dp Robolectric dialog workaround.

On a device, add a Compose service through the adapter selector, verify its five actions, and exercise backup application selection with the shared API. For a new adapter, validate the specific target only after authorization; local extension fixtures are not evidence of real deployment.


## 0.3 resource/plugin fixtures

For authorized real-host checks, use `scripts/verify-local.py` with an operator-provided private target plan and `scripts/verify-local.py`. This is opt-in and separate from `scripts/test.sh`: it contacts system SSH and the npm registry. A reviewed plan supplies observed targets; npm mutation is confined to a freshly created temporary prefix. Do not point the check at a deployed data directory.

`backend/tests/test_plugins_resources.py` exercises central plugin activation, package identities, bound versions, host relations, uninstall gates, live SSH PTY input and transient shell output. It uses temporary SQLite directories and loopback SSH fixtures; it never installs npm packages on user hosts. `ResourceTest.kt` verifies native plugin actions, package capability/confirmation UI and Console input/close callbacks through Compose semantics.

Run `scripts/test.sh` and the full Android assemble/unit-test commands after runtime changes. Use `VALIDATION-0.3.md` to distinguish built artifacts, fixture checks, browser demo checks and physical-device/real-NAS acceptance.

## OMV bind directory initialization

`bash scripts/test.sh` runs storage initialization boundary tests inside the root-owned test container. Build the 0.4.3 images using both local (`unified-application:0.4.3`, `unified-web:0.4.3`) and corresponding GHCR tags from `deploy/omv/compose.yaml`, then run `python3 scripts/test-entrypoint.py` and `python3 scripts/test-omv.py` for an isolated real-mode Compose startup/recreation test using no registered hosts. It uses temporary bind directories, a generated fixture token, a random loopback port and a unique Compose project, and cleans up its own resources. See [RELEASE-REVIEW-0.4.3.md](RELEASE-REVIEW-0.4.3.md) for current evidence and [VALIDATION-ENTRYPOINT.md](VALIDATION-ENTRYPOINT.md) for the original entrypoint verification.
