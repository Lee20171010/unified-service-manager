# API · 0.4

Application/Web/Android 0.6.0 retain API/schema v1. Both clients create Compose/npm/command plugins and copy existing manifests, alongside central GitHub catalog refresh, verified downloads and persistent custom definitions. Both clients use the same installed plugin descriptors and managed operations.

Web, Android and Application 0.4.0 add plugin document authoring. Existing resource and job APIs remain compatible; schema version stays v1.

Application `/info.version` and `/healthz.version` report 0.4.5. `api_version` remains 1; initialization does not change endpoints or request/response schemas.

All `/api/v1` resource, plugin, job and snapshot endpoints require the administrator Bearer token. `/info` and `/healthz` expose version/mode only. Tokens never appear in URLs. OpenAPI is generated in [openapi.json](openapi.json).

npm version resolution accepts a scalar or single-element JSON array from the remote npm CLI. It must resolve to one exact version; ambiguous/invalid results reject submission before queueing. The request and job response schema is unchanged.

| Method / route | Purpose |
|---|---|
| GET `/snapshot` | hosts, service-only `services`, all `resources`, plugin catalog/install state, active adapters, backups, jobs |
| GET `/plugins` | catalog metadata plus `installed` record or null |
| POST `/plugin-documents/validate` | `{manifest: object, create_only?: boolean}` → `{manifest,replaces_version,installed_version}`; validates without writes |
| POST `/plugin-documents` | same body, 201; revalidates and atomically saves to available catalog, without installation |
| GET `/plugins/{id}/manifest` | clean available manifest JSON with download filename; installed copy only when catalog source is absent |
| POST `/plugins/{id}` | `{action: install/update/enable/disable/remove/rollback}` |
| POST `/hosts` | validated host/account/key reference |
| GET / POST `/resources` | list / register `{name,host,adapter,settings}`; registration does not install software |
| POST `/resources/{id}` | edit name/settings while preserving installation identity; active work rejects edits |
| POST `/resources/{id}/bindings` | associate or update `{parent,register_command,unregister_command,verify_command}` |
| POST `/resources/{id}/jobs` | `{action,scenario?,confirm?,binding?}`; accepted job is 202 |
| POST `/services` | compatibility endpoint for service kinds only |
| POST `/services/{id}/jobs` | compatibility service operation vocabulary |
| POST `/backups` | create snapshot `{client,scenario?}` |
| POST `/backups/{id}/restore` | `{confirm:true,scenario?}` |
| GET `/jobs/{id}` | durable job envelope, fixed version and settings |
| GET `/jobs/{id}/logs?after=N` | up to 1000 chunks, increasing sequence |
| GET `/jobs/{id}/log.txt` | stream complete durable log |
| GET `/jobs/{id}/session` | transient `{phase,generation,sequence,output}` |
| POST `/jobs/{id}/session` | `{generation,sequence,data,close}`; input up to 8192 chars |
| WebSocket `/hosts/{id}/terminal` | independent terminal; authenticate in first frame |

Resource actions are server-declared: refresh/start/stop/restart/upgrade, install/uninstall/doctor, run. Binding jobs use register/unregister/verify with the binding ID. Uninstall and unregister require `confirm:true`. Missing/disabled integrations reject execution. Unknown inputs are rejected. Non-demo scenarios are rejected in real mode.

Package `settings` contain package_name, scope (`user` or `project`), directory, node, npm, version (`latest` or exact). The server resolves and freezes the version before accepting install/upgrade, rechecks configuration after resolution, and records the fixed value on the job. The loaded host version changes only after an explicit probe. Unknown references prevent package uninstall.

Job session input requires the current generation and exactly the next sequence. Duplicates/stale input are rejected; clients never automatically retry. Concurrent readers share the same input sequence. Reopening a Console attaches to the live central session. A diagnostic shell starts on the same SSH connection after the foreground command exits; it is a fresh shell. The shell buffer/raw input are not stored in SQLite. Closed/restarted sessions reject input; a missing session is returned as `phase:closed`.

Errors: 401 authentication, 404 missing record, 409 conflicting active target/identity/configuration, 422 invalid capability/configuration/lifecycle. Worker failures are durable failed jobs with output, not automatic retries. See `RUNTIME-0.3.md` for package format, rollout compatibility and runtime limits.

Plugin documents use interface v1 and a maximum canonical JSON size of 128 KiB. Unknown manifest keys, malformed field types, unsupported drivers/dependencies and same-version content conflicts return 422. Both document POST endpoints require the same admin authentication. Imported documents take precedence over supplied catalog entries with the same ID; preview reports the replaced and installed versions. Already installed files and activation stay unchanged until explicit Install/Update. Export contains integration definitions only, not host/resource instance settings or installation records. See [authoring](PLUGIN-AUTHORING.md).

Client 0.4.1 uses the same API for automatic saved-connection restoration. Transient network failures retry snapshot/job/session reads only. HTTP 401/403 requires explicit credential correction. POST mutations, job input and terminal creation are never automatically replayed.

Client 0.4.2 changes connection presentation only: server-name entry, server details and explicit credential editing. It uses Application 0.4.0 with the existing requests and authentication model.

## Plugin defaults · 0.4.5

Four service packages v1.1.0 provide Linux/systemd refresh, start, stop, restart, upgrade and doctor operations through existing descriptors. Web and Android use the same operations and fields; optional instance command overrides are under advanced settings and retain their values when collapsed. Nonempty instance commands take precedence over manifest commands; missing newly added settings receive manifest defaults. No new endpoint or schema version is introduced. See [PLUGIN-CATALOG.md](PLUGIN-CATALOG.md) for supported environments, legacy-template preservation and updates through JSON import. Android 0.4.5 carries the new form layout; Application 0.4.5 supplies the override/default semantics.

Legacy service and backup submissions share Application's plugin lifecycle lock with resource submissions. Plugin version/settings binding and durable job insertion form one guarded operation; plugin changes cannot pass their busy-job check concurrently with an older binding being queued.

Android 0.4.6 moves TLS connection disposal off the UI thread. Transient 502 responses continue to use read-only reconnect/poll retry; saved credentials and operation replay policy are unchanged. No server API or image update is required.

## Official plugin catalog · 0.5.0

GET /snapshot adds plugin_catalog {checked (Unix milliseconds or null), error, refreshing, count, source}. Plugin entries add source (builtin/github/custom/installed) and artifact_checksum for GitHub packages. Existing fields and API/schema v1 are preserved.

POST /plugin-catalog/refresh (authenticated) refreshes metadata only and returns catalog status. Network/validation failure returns status with error and preserves the prior cache. POST /plugins/{id} accepts optional version and checksum alongside action for install/update; mismatches return 422 PLUGIN_CHANGED. Both current clients submit the displayed identity. GitHub manifests download on explicit install/update or export, with fixed-origin HTTPS, size limits, content checksum and metadata checks. Downloads do not queue host operations. Busy-job locking, custom precedence, immutable installations and rollback are preserved. Older clients remain compatible; no installed plugin is automatically upgraded.

## Android adaptive UI · 0.5.1

The adaptive native layout uses existing API v1 endpoints. Window resizing and Activity recreation do not submit mutations, open SSH sessions or resend input. Draft retention is client memory only; no additional server persistence or endpoint is introduced.

## Personal plugin authoring · 0.6.0

API/schema remain v1. Compose manifests may use independent IDs with resource_kind=service, category=service-management, one compose_dir field, and a nonempty subset of refresh/start/stop/restart/upgrade. Active descriptors honor manifest identity, version, fields and operations. Settings use the declared directory default and existing absolute-path validation. Jobs for the same host/directory share installation locks across plugin IDs. New builders and full-document copies use existing export/validate/import endpoints. Copy clients send create_only=true in both document requests. Application rejects IDs present in local, GitHub or installed catalogs and repeats this check under its lifecycle guard on save. Imports default create_only=false and retain the explicit preview-and-replace contract. No endpoint activates plugins during authoring.
