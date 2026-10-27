# Validation · Unified 0.3.0 · 2026-10-27

Current client release: [Web / Android 0.3.2 validation](VALIDATION-0.3.2.md), including the user-selected icon, screenshots, APK and image distribution. Earlier client evidence below is retained for release history.

Android follow-up **0.3.1 / versionCode 6** adds the adaptive launcher icon derived from Web's `u•`. Assemble and all 22 Android tests passed. AAPT confirms icon/roundIcon plus API 26 and API 33 resources, including monochrome; APK signature matches 0.3.0 for an in-place upgrade. SVG rendering of the actual vector paths was inspected under circle/rounded-square/themed masks (`preview/android-launcher-0.3.1.png`); Z Fold launcher rendering remains device acceptance. SHA-256: `49488f4d4e9b716803cac541f9d332359917380402fc80141ab4d7a2d94e5b25`. Server/API/NAS images stay 0.3.0.

Follow-up: `scripts/verify-local.py` with an operator-provided private target plan records 17 real-host checks, 49 backend / 8 Web tests, and retained client compatibility. The initial release evidence below remains historical.

## Built and fixture-tested

- `bash scripts/test.sh`: 43 backend tests pass; 8 Web capability/theme tests pass; production JS syntax checks pass. Builds the Application image and isolated test image.
- `android/gradlew -p android :app:assembleDebug :app:testDebugUnitTest --max-workers=2`: build succeeds; 22 JUnit/Robolectric/Compose tests pass, including three new resource/plugin/interactive-console semantic tests.
- APK versionName 0.3.0, versionCode 5, debug-signed; SHA-256 published alongside the APK. No physical Android device acceptance was performed.
- OpenAPI regenerated from the running API factory.

Backend fixtures cover zero installed plugins, explicit activation and persistence, retained 0.2 records, disabled/missing/corrupt integrations, independent catalog additions without core registration, immutable versions/update/rollback, package identity deduplication across management plugins, operation allowlists, exact version binding, failed update observation preservation, host compatibility, related-target conflicts, registration/probe/uninstall gates and protected active plugin dependencies.

Isolated local AsyncSSH fixtures verify known-host checking, actual SSH exec requests for npm resolution/install/observed version, a live PTY prompt receiving input, stale/duplicate generation/sequence rejection, command exit status, the subsequent diagnostic shell, transient shell output and explicit session close. The fixture server responds to commands; these are not installations of third-party packages on user hosts. Generic command observation parsing and bounded observation output are covered by the execution contract.

## Browser verification on deployed demo

At <https://manager.example.com/>:

- Existing inventory/backups/history persisted across the upgrade. Plugin installation initially empty; 13 packages available.
- Explicitly installed bili, npm and OpenCode management integrations through the Plugin page.
- Registered `bili · Demo` with a user prefix and explicit Node/npm paths. Registration created no install job.
- Submitted Install; the central durable job retained `1.0.0-demo`, streamed progress and completed successfully.
- Entered `pwd` in the demo diagnostic shell; closing and reopening Job Console retained the same shell output without changing durable job logs.
- Registered an OpenCode demo resource, associated it with bili through a separate binding form, and submitted a distinct registration job.
- Checked type/category filters and desktop/mobile layout. Status labels distinguish installed packages from running services and show unavailable management plugins.

Browser actions used demo fixtures only. The SSH path is implemented but was not pointed at nas-host or other user infrastructure. No user package cache, OAuth pool, application configuration or real WebDAV data was changed.

## Deployment and recovery evidence

Application and Web containers are deployed on the review host with healthy Application healthcheck and the existing Tailnet 9443 endpoint. Download page 9444 publishes the new APK. Prototype 8443 remains separate. No unrelated Tailscale mappings were changed.

An online SQLite backup was taken before deployment at `/data/release-backups/before-0.3.0.sqlite3` in the demo data volume. The previous Application image content ID was already unavailable for tagging, so this host does not have a ready old-Application-image rollback. Recovery to 0.2 requires the retained database backup and a compatible 0.2 build/source. Future deployments must retain release images before replacement.

## Runtime boundaries

See `RUNTIME-0.3.md`: npm user-prefix/project scopes; administrator-configured service and binding recipes; independently probed loaded versions; JSON command/npm plugin interface; fresh diagnostic shell on the same connection after managed exit. Host-managed cache adoption, preserving the original shell process, arbitrary central executable plugin packages, production APK signing and real NAS/device acceptance are separate follow-ups.

Screenshots: `preview/runtime-0.3-plugins.png` (desktop), `preview/runtime-0.3-mobile.png` (390 × 844). Mobile navigation was verified as five items on one row, with a visible demo banner.

Published APK SHA-256: `9170f3beb612af795af7ad57cfd694b8ed456c3e7c0bbce7f60e6e8195763846`.
