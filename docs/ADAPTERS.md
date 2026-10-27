# Adapter implementation reference · delivered 0.2.0

Status: maintenance and migration reference for the deployed release. New extension work follows [PLUGINS.md](PLUGINS.md), including independent packaging, explicit installation and zero preinstalled integrations. The registration/build workflow below documents how 0.2.0 currently works.

Unified loads trusted adapters bundled into its Application image. Register implementations in `backend/unified/adapters/__init__.py`, run the contract and client checks, and publish a new image. A normal Docker Compose project uses the existing `compose` adapter: adding its host and project directory in either client is sufficient.

## Ownership and contract

`adapters/contracts.py` defines three Python protocols and shared descriptor/context/result types:

| Protocol | Implement | Responsibility |
| --- | --- | --- |
| `ServiceAdapter` | `descriptor`, `validate(settings)`, `identity(settings)`, async `execute(host, service, action, context)` | Canonical configuration, stable target identity, service execution and resulting status/version |
| `BackupApplication` | `descriptor`, `source(config)`, async `prepare(action, context)`, `validate_restore(staged)` | Configuration location, application preparation, staged configuration validation |
| `BackupStorage` | `descriptor`, `validate()`, async `upload(name, path)`, async `download(name, path)` | Deployment configuration validation and bounded archive transfer |

The Application Layer owns authentication, accepted operations, queueing, timeouts, target locks, progress, durable stdout/stderr and final job state. Adapters receive no database or HTTP handler. `JobContext` supplies `job_id`, the demo scenario, async `log(stream, text)` and async `progress(0..99)`. Successful service execution returns `ServiceResult(status, version)`; the worker persists it and completes the job at 100%. Error and cancellation paths retain the existing interrupted-job semantics. An operation is never automatically replayed.

A descriptor includes a stable ID, kind, label, implementation `version`, `interface_version=1`, supported operations and service configuration fields. The registry rejects duplicate IDs, incompatible interfaces and operations outside the shared vocabulary. IDs are lowercase letters, digits and hyphens; field names use lowercase letters, digits and underscores.

Service operations: `refresh`, `start`, `stop`, `restart`, `upgrade`. Backup operations: `backup`, `restore`. Storage operations: `upload`, `download`. New operation semantics require an intentional contract change and implementation in both clients. Existing operations and string configuration fields can be reused by a new adapter without client-specific integration code.

## Add a service adapter

1. Implement `ServiceAdapter` in a focused module. Reuse transport helpers where appropriate. Constructors receive deployment configuration or controlled dependencies.
2. Declare the supported operation subset and `ConfigField(name, label, initial, required)` entries. Interface v1 fields are plain strings. Credentials stay in deployment configuration or SSH mounts; expose only non-secret identifiers/references in service settings.
3. `validate()` rejects unknown/missing/invalid fields and returns canonical settings. `identity()` returns a stable target key within that adapter and host, so two inventory entries cannot point at the same resource. The worker serializes service jobs using the existing inventory target lock.
4. `execute()` receives a validated service record containing `settings`, plus the centrally resolved host. Use only the declared fixed operations. Quote values crossing a shell boundary. Emit credential-free output and await every operation so cancellation cannot leave detached work.
5. Register the implementation in `builtins(config)`. Supply a separate simulation implementation for demo mode. Demo must never invoke real infrastructure or fall back to it.
6. Add a fixture contract test exercising authenticated registration, operation submission, durable output, supported/unsupported actions, duplicate identity and failure behavior.

`backend/tests/test_registry.py::FixtureService` is a runnable extension example: it introduces a new `fixture` service with a `unit` field and only `refresh`, then executes through the actual API, queue and worker. `ComposeAdapter` shows the production SSH implementation. Run `docker run --rm unified-tests pytest -q tests/test_registry.py` after `scripts/test.sh` builds the test image.

The Web form and native Android form both discover service types and fields from the snapshot. Switching adapter retains the service name/host and replaces adapter-specific fields. A service whose adapter is unavailable remains visible with no managed actions. The separately authenticated host SSH Terminal remains available.

## Add an application backup adapter

Register a `BackupApplication` with a stable ID and label. Its label is the application identity embedded in Unified ZIP v1 manifests and legacy API `client` values; treat it as durable data, not freely renameable UI copy. The ID is persisted as `application_adapter` in new catalog entries.

`source()` resolves an administrator-configured directory. `prepare()` may coordinate application quiescence or reject unsafe conditions; it must not replace user configuration. `validate_restore()` examines the extracted staging directory and raises on unsupported application content. It must not mutate the live configuration. Keep dump/restore ownership and interruption behavior explicit when adding an application needing database-specific consistency.

`BackupService` owns packing, size/path/symlink checks, uploaded-content verification, catalog checksum verification, staging and previous-snapshot preservation. Application validation runs after safe extraction and before the live directory rename. Both clients discover backup choices and restore availability from the same snapshot.

Built-in `magpie` and `serverbox` adapters currently describe configuration-directory snapshots. Their application-specific validation hooks have no native-export/schema parser; operators must quiesce the application before backup/restore. Attaching a new application does not imply support for its arbitrary native export files.

## Add backup storage

Implement `BackupStorage`, register it, and set `Registry.default_storage` in the server composition root. Storage selection and credentials are deployment concerns. New records persist `storage_adapter`; restoration always resolves that recorded storage rather than the current default. Legacy records resolve to `webdav`.

`upload()` creates a new object without overwriting an existing backup. `download()` limits transferred bytes and writes only to the provided temporary path. Transport adapters retain TLS/host verification and do not follow credential-bearing redirects. The shared backup service downloads an uploaded archive and checks its checksum before accepting the backup into the catalog. Local temporary files are removed on success, failure or cancellation.

`FixtureStorage` and `test_app_restore_validation_runs_before_replacement` demonstrate the storage and application seams without using real hosts or application settings.

## Discovery and compatibility

- Authenticated `GET /api/v1/adapters` returns the image-registered catalog.
- `GET /snapshot` includes the same catalog under `adapters`, plus `backup_applications` and resource-level `operations`.
- New service input: `{"name":"App","host":"h1","adapter":"compose","settings":{"compose_dir":"/opt/stacks/app"}}`.
- The legacy top-level `compose_dir` input remains accepted. Conflicting legacy and new values are rejected. Existing records are interpreted as Compose at read time, without a bulk database rewrite; Compose records retain `compose_dir` for older clients.
- Existing backup catalog entries resolve by their application label and use WebDAV. Manifest format and SQLite schema remain version 1.
- Clients show only recognized operations declared by the server. Missing capabilities fail closed. Server enforcement runs both before enqueueing and immediately before execution.
- Upgrade the server before clients. The 0.2 clients require the adapter-capable snapshot for operation controls. Older clients can continue operating the built-in Compose/Magpie/ServerBox paths but cannot discover new adapter types.

## Release and rollback

Adapters are code reviewed and shipped with the image. Installation, arbitrary module paths, hot loading, package upload and frontend code execution are not exposed through the API. This is an in-process trusted-code boundary, not a sandbox for third-party code.

Before an upgrade, stop the stack and copy its SQLite data directory and deployment configuration. Verify the new image in a separate demo volume first. Existing Compose-only databases need no migration. Rolling back to a pre-adapter release after adding new adapter types requires restoring the pre-upgrade database copy; old clients/servers cannot interpret those resources. Retain any independently created backups and previous snapshots when restoring a database copy.

Run `scripts/test.sh`, Android local tests/build and the device acceptance sequence in `TESTING.md`. Cover both clients when introducing new field types or operation semantics. Record separately fixture evidence, device results and authorized real infrastructure acceptance.
