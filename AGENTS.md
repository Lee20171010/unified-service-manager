# Unified Service Manager — contributor contract

Read `README.md`, `docs/ARCHITECTURE.md`, and `docs/HANDOFF.md` before changes.

- `backend/unified/application.py` owns use cases and job lifecycle. HTTP handlers and clients do not execute host commands or implement backup policy.
- Web and native Android are equal clients. Every new operation must appear in both clients and `docs/PARITY.md` in the same change.
- Real mode has no demo fallback. Keep separate database volumes and enforce stored mode identity.
- Run exactly one worker per SQLite data directory. Preserve unique active-target locking, durable logs, and interrupted-job recovery. Never automatically replay a failed/interrupted operation.
- SSH host-key verification stays enabled. Managed operations use declared operation IDs and validated plugin parameters. Administrator-authored service command/script definitions belong to the installed-plugin configuration path; interactive arbitrary commands use authenticated Terminal Gateway or central job diagnostic sessions. Never interpolate unquoted values into a shell command.
- Credentials belong in `.env`, read-only SSH mounts, or Android Keystore. Never commit them, include them in screenshots, put them in URLs, or print them in logs.
- Before every commit, review its complete staged diff for secrets and private information, including host/device identities, Tailnet addresses, local paths, screenshots and logs. Before a GitHub push/publication, review every commit being published and the complete reachable content being introduced; reviewing only the final tree is insufficient. Before publishing images, inspect build inputs, all image layers, image history/configuration and metadata for secrets/private data. Removing a file in a later commit/layer does not remove earlier exposure. Record the exact commit/image identifiers reviewed; do not claim publication-safe status from ignore rules or a partial scan. Publication requires completed review and user-authorized scope.
- Backup restore validates manifest, application, checksum, entry paths, limits, and symlinks before replacing configuration. Preserve the prior snapshot and fail before mutation on invalid archives.
- Do not test against real hosts or user application settings without a concrete target authorization. Use test fixtures or demo mode.
- Preserve `prototype/` as the accepted UI reference. Production source is `web/`; `artifacts/` is distributable outputs only. Never serve the repository root over HTTP.
- Scope stays single administrator, plugin-based service/package/tool management, jobs, configuration snapshots, plugin installation/lifecycle, and a line-oriented SSH terminal. Follow `docs/PLUGINS.md`: independent categorized packages, zero installed plugins on a fresh instance, explicit Plugin-page Install before integration capabilities appear, and shared server installation state for Web/Android. Catalog availability must not activate a package. No scheduling, billing, public marketplace, account roles, or full terminal emulator unless requested.
- When behavior changes, update handoff notes, parity, API contract, and tests. Run `scripts/test.sh` and `android/gradlew -p android :app:assembleDebug :app:testDebugUnitTest` as relevant.
- Native UI behavior uses Compose semantics tests with Robolectric; coroutine races use controlled clients and virtual time. See `docs/TESTING.md`. Keep real-device acceptance separate from local JVM results.
- No installed `rtk` is available on the current host; use standard commands unless it becomes available.

Current acceptance: authenticated API, runnable Compose stack, backend tests, Web UI integration checks, a successfully built APK, and reproducible handoff documents. Report separately what was built, tested in fixtures, tested on device, and deployed to real infrastructure.

- Runtime plugin work follows `docs/RUNTIME-0.3.md`; `docs/PLUGINS.md` retains the broader target specification; `docs/ADAPTERS.md` is the delivered 0.2.0 maintenance/migration reference. Keep capability enforcement in Application, and shared archive/checksum/restore validation in BackupService. Provide fixture proof for a new implementation and preserve existing record resolution.

- Managed-object capabilities and package/host relationships follow `docs/MANAGED-RESOURCES.md`. Keep installing a Unified management plugin separate from installing remote software; record installation scope and loaded host versions independently.
