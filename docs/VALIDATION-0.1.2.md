# Validation · 0.1.2

Recorded 2026-10-27 (Asia/Taipei), on the the review host review host.

## Reproducible checks

| Check | Result | Evidence |
| --- | --- | --- |
| `bash scripts/test.sh` | Passed: 18 backend tests, 4 Web appearance tests; all three Web scripts pass Node syntax checks | `backend/tests/` |
| Compose build/start | Application healthy; Web running on loopback 4180 | `compose.yaml`, `compose.demo.yaml` |
| Tailnet HTTPS | `/healthz` and `/api/v1/info` return version 0.1.2, mode demo | Port 9443 review endpoint |
| Android assemble + local tests | `BUILD SUCCESSFUL`; 15 tests, 0 failures/errors/skips: 2 API, 6 state, 5 screen, 2 appearance | `android/app/build/test-results/testDebugUnitTest/TEST-*.xml` (generated) |
| APK signature | `apksigner verify --verbose` succeeds; v2 signature, one signer | Debug review APK |
| APK download | HTTPS download on port 9444 matches the built APK SHA-256 | Hash below |
| API contract | Exported from the built Application image | `docs/openapi.json` |

APK SHA-256:

```text
86e4a4add479abc7e4315aa83ff96afbb22fd6c700fef11806a426f8e22b2c44
```

The test suite reports one Starlette deprecation warning for its httpx-based TestClient. There are no failed tests. Review that test dependency integration during the next dependency update.

Android package metadata is versionName `0.1.2`, versionCode `3`; its signing certificate matches the preserved 0.1.0 review APK. The final command was `:app:testDebugUnitTest :app:assembleDebug --max-workers=1` with JDK 21.

## Follow-up regression evidence

- Two backend tests first failed on unclosed SQLite connections and service state remaining online after interruption. Both pass after deterministic connection closing and transactional state invalidation.
- Four initial Android state tests reproduced duplicate submissions, failed transport cleanup, stale workspace errors and stale Terminal output. All six final state tests pass, including polling cancellation and reopening the same Job Console while an earlier log request is pending.
- Five Compose tests pass with a local Robolectric API 28 runtime. These exercise service callbacks, restore confirmation, both backup clients, navigation restoration, connection dialog persistence and Terminal input. The connection-dialog test uses the documented upstream runtime workaround in `TESTING.md`.
- The 0.1.2 Application container was recreated with the existing demo volume. The authenticated service continues to expose the existing workspace over HTTPS; the downloaded 0.1.2 APK matches the local checksum.

## Appearance acceptance · 0.1.2

- All four Web tests pass: first paint/OS changes, persistence and explicit overrides, cross-tab preference updates, and invalid/unavailable storage.
- Both native appearance tests pass: default/persisted preferences and Compose toolbar/dialog controls changing the rendered palette, including live OS changes and explicit overrides.
- Live Tailnet Web inspected in light and dark modes. Dark service forms and Job Console have readable text, fields and controls. Reload retains the selected dark mode; the final selector was returned to system.
- At 390 px viewport width, document scroll width is 375 px (no horizontal overflow). The header selector remains available. Browser error log is empty after verification.
- Screenshots: `preview/theme-light.png`, `preview/theme-dark.png`, `preview/theme-console.png`, `preview/theme-mobile.png`.
- Android theme behavior is verified in Robolectric; status/navigation bar contrast and system setting changes on physical Android hardware remain device acceptance items.

## Browser acceptance

Verified through the real HTTPS review endpoint during 0.1.0 acceptance, with the server's demo execution adapter. The operation handlers and API payload contracts remain unchanged in 0.1.2; these functional checks remain applicable:

- Service restart submits a job and reaches success with persisted output.
- Flutter ServerBox backup creates a catalog entry. Closing the console and reloading the page preserves its result.
- Restore requires explicit selection confirmation and reaches success with stdout in Job Console.
- A job interrupted during an Application container rebuild is recorded as failed with `SERVER_STOPPED`; it is not silently retried.
- Host detail opens the distinct Interactive SSH Terminal. Its WebSocket demo gateway responds to `help`.
- Desktop overview and 390 px Web layout inspected. No horizontal page overflow; no browser JavaScript errors in the final acceptance session.

Screenshots: `preview/v1-web.jpg`, `preview/v1-web-mobile.jpg`, `preview/v1-job-console.jpg`.

## Adapter evidence and remaining acceptance

The backend tests include a local AsyncSSH server with host-key verification and stderr, and an HTTP transport fixture for WebDAV PUT/GET/checksum. They also cover archive traversal rejection, previous-directory preservation, conflicting jobs, and draining filesystem work before cancellation releases a target lock.

**Real nas-host deployment and Android device execution have not been performed.** No Android device was attached, and the host has no complete emulator installation. The local Robolectric tests are not device or emulator execution. The APK is built and debug-signed, with connection defaults pointing to the review environment. Validate keyboard insets, Android Keystore, log export, tailnet networking and lifecycle behavior on the intended device before a production release; follow the sequence in `TESTING.md`.

Real-target acceptance requires the actual SSH accounts, verified host fingerprints, Compose directories, WebDAV collection and application configuration paths. Run refresh first, then a deliberately selected service operation, followed by a disposable configuration backup/restore round trip. Confirm application consistency and schema compatibility separately. Unified ZIP v1 snapshots do not imply compatibility with arbitrary native Magpie or ServerBox export files.
