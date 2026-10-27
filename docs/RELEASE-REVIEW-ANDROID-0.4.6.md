# Android release review · 0.4.6

Android 0.4.6 (versionCode 14) fixes a crash while disposing pooled HTTPS connections after temporary server errors or closing a workspace. Application/Web images remain 0.4.5. Existing API, database, plugin and deployment configuration remain compatible.

## Cause and fix

A diagnostic report identified NetworkOnMainThreadException in OkHttp connection-pool eviction after HTTP 502. Closing a TLS connection can write a close_notify message. Api.close now marks the transport closed once and schedules cancellation and pool eviction on its owned OkHttp executor, which remains available after ViewModel cancellation. New calls on a closed transport are rejected. HTTPS verification, credential handling, request timeouts and operation retry policy are preserved.

## Verification

- Two real HTTPS JVM regressions (502 and successful response) failed before the fix because socket disposal ran on the caller thread, then passed with the fix.
- All 47 Android JVM/Compose tests passed, including virtual-time 502 recovery with saved credentials retained.
- All three isolated Android 16 emulator checks passed: connection editing/error recovery; real loopback HTTPS 502 followed by automatic recovery and successful-pool disposal under main-thread network StrictMode; and diagnostic export preview after a system-induced crash/restart.
- The distributable APK built with application ID dev.unified.app, versionName 0.4.6 and versionCode 14. Its signature verifies and matches the 0.4.5 signing certificate. This remains a debug APK.
- Source and extracted APK payload scans found no secrets or private deployment markers. MockWebServer and fixture certificate utilities are test-only and absent from the distributable APK. Production TLS and hostname verification remain enabled.

APK SHA-256: `7012ad02f5fedc0caf30920b1adf6726a447fa9d4d6e2d3cc146dfc1cb02eec0`.

The release asset release-evidence.json identifies the reviewed source commit/tree and APK checksum. The complete staged change and public commit ancestry receive security/privacy review before publication. Raw diagnostics, local runtime addresses and emulator reports remain outside public source and assets.

## Acceptance boundary

Emulator checks use an isolated package, synthetic credentials and a loopback HTTPS fixture. They do not exercise a user's NAS, managed services or physical phone. Backend/Web are unchanged; their 0.4.5 evidence remains in RELEASE-REVIEW-0.4.5.md. This Android-only release does not rebuild or publish Docker images. Install the APK over the prior app to retain its saved connection; no Compose or environment changes are needed.
