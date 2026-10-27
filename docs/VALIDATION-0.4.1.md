# Client validation · 0.4.1

Application remains 0.4.0; Web/native Android 0.4.1 add saved connection restoration and foreground recovery.

- Web: 14 tests passed. New tests cover reopening with persistent credentials, failed replacement preserving the prior connection, session-only migration and unavailable browser storage fallback.
- Android: 33 tests passed before packaging. Six new ViewModel tests use controlled clients and virtual time for cold start/process recreation, first-run defaults staying inactive, offline retry, background/resume retaining selected console, expired token stopping retries and cancellation of an unfinished automatic connection. Existing stale-response, no-duplicate-write, UI and plugin tests remain green.
- Lifecycle cancellation issues no new read requests in the background; foreground resumes immediately. Network recovery clears only connection errors, preserving operation failures. Tests assert no management writes are replayed.
- Cold process recreation fetches fresh server state using saved credentials. Surviving ViewModels retain inventory and job console; saveable page/filter state is keyed by workspace URL. Independent SSH shell connections and expired job sessions require explicit reopening, not automatic command replay.

The APK uses the existing application ID and debug signing key. Physical Android process-kill/file-picker acceptance and nas-host deployment remain separate from JVM simulations. Backend code and data schema are unchanged, so the prior 66 backend tests remain the applicable evidence rather than a newly claimed run.
