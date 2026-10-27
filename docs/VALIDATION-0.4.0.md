# Validation · 0.4.0

Release scope: Web/native Android command-plugin creation, JSON file/pasted import with server preview, persistent available catalog and JSON export. Installation remains explicit.

## Automated evidence

- `bash scripts/test.sh`: 66 backend tests and 10 Web tests passed. Covers import persistence, preview without writes, explicit install/job execution, export, same-version conflict, installed-version stability until update, rollback, malformed document rejection and authentication.
- `scripts/package-android.sh`: APK 0.4.0, versionCode 8 built; all 27 Android tests passed, including five plugin editor tests for preview/save separation, retained errors, command/parameter form wiring, export loading and bounded document reads.
- The initial native long-form AlertDialog repeatedly laid out under Robolectric. A bounded, scrollable Dialog using the existing Console layout pattern resolves it; bottom actions remain visible. No test timeout relaxation was used.
- Browser verification on local demo: command form with a custom choice parameter → server preview → save as uninstalled; export JSON download → file chooser import → preview → save; pasted import preview; reload persistence. A clearly named `ui-authoring-example` remains available and uninstalled as a review example.
- Desktop and 390×844 browser layout checked; mobile scrollWidth 375 <= viewport 390, dialog width 366. Preview body scrolls and action buttons remain visible. Screenshots: `preview/plugin-authoring-0.4-desktop.png`, `preview/plugin-authoring-0.4-mobile.png`.
- local demo Application/Web updated to 0.4.0 after online SQLite backup to `/data/release-backups/before-0.4.0.sqlite3`. Prior backend/Web images retained as `*:before-0.4.0` (backend uses retained 0.3.0-omv1 release image). No real user services changed.

## Boundaries

Backend integration tests use isolated demo state and existing SSH fixtures. No new tests execute commands on real user services or modify their configurations. Android file-picker/device acceptance and nas-host deployment are separate from local JVM/build evidence.

## Reproduction

Run `bash scripts/test.sh`, then `android/gradlew -p android :app:assembleDebug :app:testDebugUnitTest --max-workers=1`. `scripts/export-api.sh` regenerates the API contract. `scripts/package-android.sh` and `scripts/package-omv.sh` build downloadable artifacts; OMV users load the prebuilt image bundle and paste the supplied Compose/env.
