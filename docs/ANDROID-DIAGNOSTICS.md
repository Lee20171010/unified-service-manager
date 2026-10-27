# Android diagnostic reports

Android 0.4.4 adds local diagnostic reports for connection and crash investigation. It works with the existing Application/Web 0.4.3 deployment; no NAS image or configuration update is needed.

## Reproduce and export

1. Install the updated APK over the existing app to retain the saved connection. Do not uninstall or clear app data.
2. Open the server name at the top right, then **診斷日誌**. This entry also works before connecting. Optionally clear older diagnostic entries before a new reproduction.
3. Close the dialog, edit the connection and reproduce the failure.
4. If the app exits, reopen it. Open **server name → 診斷日誌 → 匯出 .txt** and choose where to save `unified-diagnostics.txt`. **分享** opens Android's text share sheet instead. Preview the report before sharing it with a maintainer.

No report is uploaded automatically. Clearing diagnostic logs does not change the saved server, token or managed services.

## What is recorded

- App version, version code, Android API level and event timestamps.
- Activity lifecycle and manual/automatic connection phases: URL validation, snapshot request, parsing, credential persistence and activation.
- Failure exception classes, bounded code frames and HTTP status when available.
- JVM uncaught exceptions, recorded before delegating to Android's original crash handler.
- Android's previous process-exit reason on API 30+, without the system's raw trace or description. `PREVIOUS_EXIT number` is the platform reason code; `APP_START number` is the app version code.

The store retains up to 200 events and 64 KiB in app-private, backup-excluded storage. Older entries are removed. Export does not include server URLs/IPs, tokens, account names, credentials, response bodies, exception messages, command/job output or source filenames. Code symbols and line numbers are retained for diagnosis. This is separate from the server-owned Job Console and its full operation logs.

## Limits and maintenance

An uncaught JVM exception can provide a code stack. Native crashes, ANRs, forced stops and abrupt power loss may provide only the last recorded phase and a system exit reason; this feature does not collect unrestricted logcat or promise a complete stack for every exit. Storage failures are best effort and must not replace the original application failure.

`Diagnostics.kt` owns fixed event fields, retention, persistence and the crash handler. `UnifiedApplication` initializes it before any Activity; `MainViewModel` records connection phases without passing user input to the logger. `DiagnosticsDialog.kt` previews, clears, shares and saves reports through the Android document picker. Backend/API behavior is unchanged. Use the tests and shared-emulator wrapper workflow in [TESTING.md](TESTING.md).

Android 0.4.6 fixes a diagnosed crash when a temporary HTTP error is followed by pooled TLS cleanup on the main thread. A report showed HTTP 502 followed by NetworkOnMainThreadException in ConnectionPool eviction; the endpoint later recovered. Cleanup now runs on the transport executor. This fixes the client crash; a persistent HTTP 502 still requires investigation of the server/proxy. No raw user diagnostic report is stored in the public repository.
