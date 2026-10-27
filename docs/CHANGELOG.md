# Changes

## 0.4.3 · public release security review

- Anchor configuration backup reads to verified descriptors, reject raced path replacement and special files, enforce actual byte/traversal limits, and add seven regression cases.
- Deny third-party framing of the Web interface through CSP and X-Frame-Options.
- Remove private deployment defaults and references, keep Android first-run connection fields empty, and exclude private runtime/validation artifacts from publication.
- Restrict Docker build input, add commit/image publication checks, and publish reviewed versioned images through a manual GitHub Actions workflow.
- Update pinned Alpine runtime bases and security packages; remove unused Python installation tooling from the Application runtime. Both final local images have zero Trivy findings at review time.

## Application 0.4.2 · container entrypoint

- Application initializes its writable directories inside the image, then execs the server as UID/GID 10001 with zero capabilities and no-new-privileges. Uses setpriv already present in the pinned base image.
- Compose contains application and web only. Existing files and read-only SSH mounts are preserved; explicit non-root user overrides remain supported.
- Entry-point contracts and isolated Compose checks cover permissions, exact arguments, failure before startup, persistence, authentication and graceful shutdown. Web/APK remain 0.4.2.

## Docker release naming · Application 0.4.1 / Web 0.4.2

- Use platform-independent numeric image tags and archive names. The current images are exact retags of the previously distributed payload, allowing existing users to migrate without downloading or duplicating layers.
- Compose, packaging, download links and deployment instructions use the current tags. Packaging exports existing immutable releases rather than rebuilding under a published name.
- See `VALIDATION-RELEASE-0.4.2.md` for ID equality, compatibility and deployment verification.

## OMV deployment revision omv2

- Application image `0.4.0-omv2` adds a one-shot storage initializer; main Application stays UID 10001. Web/APK remain 0.4.2.
- Manual OMV Compose uses `./data`, `./ssh`, `./sources`; fresh directories initialize automatically, without USM_ROOT or shell permission setup. Existing populated directories and file permissions are preserved.
- Added isolated Compose startup/recreation coverage and permission-boundary unit tests. Existing deployments retain their original host paths. See `VALIDATION-OMV2.md`.

## Web / Android 0.3.2 · selected brand

- Applied the user-selected circular-node U artwork to both clients, browser icons, the native header and adaptive/themed launcher resources. Android versionCode 7 uses the existing signing key.
- Published Web image `unified-web:0.3.2-omv1`, a Web-only upgrade archive, and refreshed manual OMV Compose/env downloads. Application image `0.3.0-omv1`, API and persisted data remain compatible.

## Android 0.3.1 · launcher icon

- Added an adaptive launcher icon based on the Web's dark-green `u•` mark, including round launcher masks and the Android 13+ themed-icon layer. The previous Manifest omitted the application icon.
- Native versionCode 6 retains the application ID and signing key for an in-place upgrade. Application/Web remain 0.3.0; the existing NAS images are compatible.

## 0.3.0 · 2026-10-27 local validation fix

- Accept a single-element version array from npm 12 while retaining scalar compatibility and rejecting ambiguous responses. Actual host testing reproduced the previous install/upgrade submission failure.
- Add an opt-in real SSH acceptance script, reviewed local target plan and evidence. Verified existing resources, loaded bili version, real npm install/upgrade/uninstall in an isolated prefix, and interactive job input/failure/interrupt behavior. See `scripts/verify-local.py` with an operator-provided private target plan.

## 0.2.0

- Introduced versioned, image-bundled service, backup application and storage adapter contracts and explicit registration. Built-ins cover Docker Compose, Magpie/ServerBox configuration snapshots and WebDAV.
- Application services retain jobs, target locking and durable logs; backup services retain common archive, checksum and restore policy. Demo execution uses explicit simulation paths.
- Web and Android discover service configuration fields, supported operations and backup choices from the same server catalog. Unavailable capabilities fail closed in clients and at submission/execution on the server.
- Existing Compose input/records and backup catalogs resolve compatibly without a bulk rewrite. Added a runnable custom service/application/storage fixture and contract tests. See `ADAPTERS.md` for extension and rollback instructions.
- API v1 gains authenticated adapter discovery and additive snapshot fields. SQLite schema and archive format remain v1. Android versionCode is 4.

## 0.1.2

- Web and native Android offer light, dark and system appearance, defaulting to the OS. Explicit choices persist locally; system changes apply while the client is open. Web tabs synchronize their preference.
- Panels, forms, status labels and console controls use readable theme colors. Terminal output keeps its own dark palette. Android system bars use the resolved appearance.
- Added Web preference/OS-change tests and native persistence and Compose selection/palette tests. API v1 payloads and SQLite schema remain unchanged. Android versionCode is 3.

## 0.1.1

- SQLite connections close at transaction exit, including failure paths. Interrupted service jobs atomically mark their service state as unknown so that both clients require a fresh status read.
- Android ignores delayed failures from a previous workspace and delayed frames from previous Terminal sessions. Reopening Job Console resets its response generation as well as its log cursor.
- Repeated native submit events are coalesced while a request is in flight. Failed connection candidates release their transport; the active connection is only replaced after verification and credential storage succeed.
- Connection dialogs preserve their fields until a successful connection. Switching workspace resets selections and forms. HTTP transport does not automatically retry operations or follow redirects.
- Added transaction/shutdown regressions, controlled coroutine state tests and local Compose behavior tests. See `TESTING.md` and `VALIDATION.md` for evidence and remaining device acceptance.

API routes, request payloads, SQLite schema v1 and backup format v1 are unchanged. The 0.1.0 APK remains available in the review artifact directory for comparison; the 0.1.1 APK uses versionCode 2 and the same local debug signing key.

## 0.1.0

First runnable Application Layer, Web service and native Android review APK, with Docker Compose and documented handoff boundaries.

## 0.3.0 · 2026-10-27

- Added explicit central plugin installation, independent manifest directories, persisted activation, immutable versions and rollback. Existing records remain; migrated instances require manual plugin installation.
- Added managed package/extension/tool resources, descriptor fields/choices, editable version policies and commands, npm version resolution, install/update/uninstall, and scope identity checks.
- Added compatible host bindings, independent installed/loaded versions, explicit registration/probes and related-target locks.
- Added worker-owned job PTY input with generation/sequence checks and transient diagnostic shells. Console dismissal detaches without closing the central session.
- Delivered equivalent Web and native Android controls and Android versionCode 5. Detailed limits: `RUNTIME-0.3.md`.

## 0.4.0 — UI plugin authoring

Web and native Android can create command integrations with custom parameters, import JSON files or pasted documents, preview central validation, and export available manifests. Imported documents persist under the existing data volume; installation and updates remain explicit. Backend validates document types/size and immutable versions before atomic replacement, while installed versions and job execution remain separate. Application/Web/APK require one 0.4.0 upgrade; subsequent supported plugin changes require no rebuild.

## Clients 0.4.1 — automatic connection and foreground recovery

Android automatically connects a previously saved workspace when foreground observation starts, including after process recreation. Background pauses polling; returning refreshes immediately while retaining the current view and console. Temporary network failures keep state and retry reads; 401/403 waits for corrected credentials. Web persists only successfully validated settings per origin, migrates session-only settings and refreshes on visibility/online events. Operation and terminal-input writes are never replayed. Application remains 0.4.0.

## Clients 0.4.2 — server connection presentation

A compact server-name entry opens server/address details in Web and Android. Credential editing is a separate action. Repeated successful-connection labels and implementation-layer wording are removed from daily screens. Demo indicators and recovery/error messages remain visible. Single-workspace automatic connection, persistence, API and transport behavior remain unchanged.
