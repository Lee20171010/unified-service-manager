> Current 0.3 build and deployment evidence: [VALIDATION-0.3.md](VALIDATION-0.3.md). The entries below retain earlier release evidence.

# Validation · 0.2.0

Recorded 2026-10-27 (Asia/Taipei), on the the review host review host.

## Checks

| Check | Result | Evidence |
| --- | --- | --- |
| Before refactor | 18 backend tests, 4 Web theme tests passed | Existing behavior baseline |
| `scripts/test.sh` | 30 backend tests and 7 Web tests passed; script syntax checks passed | `backend/tests/`, `tests/` |
| Android local tests | 19 tests; 0 failures/errors/skips | 2 API, 6 state, 5 screen, 2 theme, 4 adapter |
| Android APK | `assembleDebug` succeeded, versionName 0.2.0 / versionCode 4 | `artifacts/unified-0.2.0-debug.apk` |
| APK signature/download | v2 signature verified; Tailnet download matches local SHA-256 | Port 9444 |
| Compose | Application healthy and Web running | Existing demo data volume retained |
| API | `/healthz` reports 0.2.0; authenticated adapter catalog and snapshot available | Port 9443 |
| Contract snapshot | Exported from final Application image | `docs/openapi.json` |

APK SHA-256:

```text
021ab7c90ac88a8f9212abfcf5d3b24dac61017bddd8497dc2c6563f1f3c747d
```

The suite still reports the existing Starlette httpx TestClient deprecation warning. Android tests run locally with Robolectric API 28 and controlled coroutines; they are not device/emulator execution. The final binary was assembled after changing release metadata to versionCode 4; the preceding complete test/build run passed all 19 tests on the same behavior sources.

## Adapter evidence

- A fixture service with a new ID, `unit` field and only `refresh` was registered without modifying Application routing. Authenticated API creation and the real worker executed it, retained stderr and saved the returned status/version.
- A new application and in-memory storage completed a configuration backup/restore round trip through the API. Storage switching does not change which provider restores an existing archive.
- Server enforcement rejects unsupported actions, unknown types and invalid settings before enqueueing. The worker also rechecks capabilities; removal after enqueue causes an explicit failure and releases the target lock.
- Duplicate adapter IDs, unsupported interface versions/verbs and duplicate service identities are rejected. Discovery exposes descriptor metadata without deployment credentials.
- Legacy Compose input and records still resolve correctly. Reading an old record does not rewrite it. Conflicting legacy/new settings are rejected.
- Application restore validation runs on extracted staging data before replacement; rejection preserves the live configuration. Existing traversal, symlink, checksum, previous-snapshot and cancellation tests continue to pass.
- Demo tests prohibit real SSH, storage transfer and application preparation hooks while service/backup/restore jobs still succeed.
- Web tests cover operation subsets, dynamic service/application discovery, settings serialization, unsupported interface versions and absent capabilities. Native Compose tests cover visible read-only actions, switching form types without stale settings, and a new backup application choice.

## Review deployment and browser acceptance

The existing demo workspace contained 3 hosts and 6 services with no pending jobs before deployment. A consistent SQLite backup was saved inside the demo volume as `/data/pre-adapters-0.1.2.sqlite3` before recreating containers. The workspace remains in demo mode; none of these targets represent a newly connected real host.

The HTTPS Web UI shows the installed Docker Compose type and its project-directory field in Add Service. Existing Magpie details resolve to the Compose adapter and show the five declared actions, with a separate SSH Terminal entry. A demo restart completed through Job Console with progress and stdout. Backup creation choices still include Magpie and Flutter ServerBox, sourced from the registry. Screenshots are stored under `preview/adapters-*.png`.

## Remaining acceptance

Real nas-host deployment and Android physical-device execution have not been performed. Native APK is debug-signed. Device acceptance should cover the adapter selector/form, supported operations, theme/system bars, keyboard insets, Keystore and tailnet networking, as described in `TESTING.md`.

The bundled Magpie/ServerBox adapters implement Unified ZIP v1 configuration snapshots. Application-specific native export parsing and automatic quiescence are not implemented. Actual source locations and consistency rules must be confirmed for authorized real deployment.

Prior acceptance evidence: [0.1.2 validation](VALIDATION-0.1.2.md). Development, compatibility and rollback rules: [Adapter guide](ADAPTERS.md).
