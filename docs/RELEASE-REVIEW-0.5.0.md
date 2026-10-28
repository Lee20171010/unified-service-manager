# Release review · 0.5.0

Application, Web and Android 0.5.0 separate generic builtins, the official GitHub catalog, user definitions and installed packages. API/schema v1 and existing installed resource settings remain compatible. Android versionCode is 15.

## Reviewed behavior

- Compose, generic npm and WebDAV definitions ship at /builtin-plugins. Eight specific software definitions are available through the fixed official GitHub metadata index. Refresh at startup/every six hours and the manual client action update metadata only.
- Explicit Install/Update downloads a size-bounded package over verified HTTPS without redirects or administrator credentials. SHA-256, manifest schema and metadata must agree before activation. Both clients pin the displayed version/checksum. Installed copies remain local and usable offline.
- Downloads occur outside the Application lifecycle lock. Final commit rechecks the complete selection, including installed state, and checks active jobs inside the write transaction. A delayed update cannot overwrite a subsequent disable/remove or a custom import. The original job/version binding regression remains covered.
- Exact historical factory definitions in legacy volumes no longer mask official entries. Modified legacy documents copy into data after the single-worker lock, without overwriting UI imports. Unreadable source documents remain isolated. Original files and installed versions remain available for rollback.
- Shutdown cancels durable work before waiting for an in-flight catalog refresh. No management command or installation is automatically replayed.

## Verification

| Check | Result |
| --- | --- |
| Backend fixtures | 119 passed, including 23 catalog/migration/lifecycle checks and the original submission race regression |
| Web tests | 17 passed; source/error rendering and pinned action bodies included |
| Android JVM/Compose | 48 passed; 0.5.0 debug APK built with normal dev.unified.app identity |
| Android 16 emulator | Four isolated checks passed: connection switching, real HTTPS error/recovery, catalog display/check/install callbacks, and diagnostic persistence after crash/restart |
| Container fixtures | Initialization, UID/GID 10001, zero server capabilities, read-only SSH, authentication, explicit plugin activation and recreation persistence checked |
| Package artifacts | Generated index/content-addressed JSON consistency and package validation checked using local fixture transports |
| APK privacy | Extracted payloads and manifest scanned; no secret/private-deployment markers or test certificate/server classes found |

APK SHA-256: `f37f10bcb492afa34f3d1cab995d9d24365379b917179372eec03a26e30dcc07`. This remains a debug APK, signed with the same certificate as the preceding release.

Astra/max independently reviewed the source boundary and fixes for download locking, legacy read errors, delayed reactivation and shutdown ordering. Final staged-tree and public-ancestry review precede publication. The commit-bound publication workflow repeats regressions, container checks, every-image-layer secret scanning and High/Critical vulnerability gates before publishing numeric and latest tags. Release assets identify the exact reviewed commit/tree, APK checksum and published image digests.

The loopback SSH prompt fixture waits for readiness with a bounded timeout rather than a fixed iteration count, retaining error propagation under host contention. No user host, service command, NAS deployment or real WebDAV restore was exercised by these checks. Physical-phone installation remains user acceptance; emulator fixtures use an isolated package and synthetic credentials. User diagnostics and private deployment records are excluded from public artifacts.

## Upgrade

Use the same data/ssh/sources paths and Compose project identity. Pull and recreate both 0.5.0 images (or latest after publication), then install the APK over the existing app. Keep the compatibility catalog mount during transition. Official metadata refreshes automatically; Install/Update remains explicit. UI imports retain priority over same-ID official entries. See PLUGIN-CATALOG.md and OMV-COMPOSE.md for the current storage and offline behavior.
