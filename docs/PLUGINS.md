# Plugin lifecycle — accepted target specification

Status: product design specification. UI creation/import/export delivered in 0.4 is documented in [PLUGIN-AUTHORING.md](PLUGIN-AUTHORING.md). The delivered 0.3 subset and precise execution boundaries are documented in [RUNTIME-0.3.md](RUNTIME-0.3.md); use that document for current deployment and package authoring. This specification also retains future refinements.

## Product contract

Every integration is an independently packaged plugin. The project may publish ready-made plugins, but publishing or making a package available does not install it. A fresh Application instance starts with zero installed plugins in both real and demo modes.

The administrator installs a plugin explicitly from the Plugin page. Successful installation makes its capabilities available to both Web and Android through the shared Application Layer. Installation is server-wide: clients do not install their own copies. Package installation, service definitions and supported plugin updates require no rebuild of the central Application image.

The core owns hosts, authentication, plugin lifecycle, validated parameter binding, jobs, concurrency locks, persistent logs, transport primitives and shared backup integrity policy. Integration-specific commands, scripts, configuration schemas, status parsing and application definitions belong to plugin packages. Core transport support alone does not expose a selectable integration.

## Categories and package identity

The initial application coverage is defined in [REQUIREMENTS.md](REQUIREMENTS.md), including OpenCode, OpenChamber, Hermes and ChatGPT service/package management, Magpie and Flutter ServerBox backups, and configurable integration of halogen service, android-test-env, xpu-mode, zentune and future tools.

| Category ID | Display name | Published packages initially planned |
| --- | --- | --- |
| `service-management` | 服務管理 | OpenCode; OpenChamber; Hermes; ChatGPT; Docker Compose; generic SSH command/script service management |
| `package-management` | 套件與應用插件 | npm 套件管理; bili / billion-context; oc-codex-multi-auth |
| `application-backup` | 應用備份 | Magpie; Flutter ServerBox |
| `backup-storage` | 備份儲存 | WebDAV |

Categories describe an integration's purpose. Source/author and installation status are separate metadata. First-party and third-party packages use the same install flow. A package has one primary category initially; optional tags can support discovery without changing its ID.

Each plugin has a stable, globally unique ID, an independent package version, a supported Plugin API version, a category, a display name, a description, an author/source and optional declared plugin dependencies. Category or display-name changes do not change plugin identity or move installed resources. IDs and versions are validated before becoming filesystem paths.

## Folder layout

Each developed plugin has its own self-contained folder. Proposed repository layout:

```text
plugins/
  service-management/
    opencode/
      plugin.yaml
      README.md
      LICENSE
      scripts/
      tests/
    openchamber/
      plugin.yaml
      README.md
      ...
    hermes/
      plugin.yaml
      README.md
      ...
    chatgpt/
      plugin.yaml
      README.md
      ...
    docker-compose/
      plugin.yaml
      README.md
      LICENSE
      scripts/              # optional executable implementation
      assets/               # optional icons
      tests/                # package contract fixtures
    ssh-service/
      plugin.yaml
      README.md
      ...
  package-management/
    npm-packages/
      plugin.yaml
      README.md
      ...
    billion-context/
      plugin.yaml
      README.md
      ...
    oc-codex-multi-auth/
      plugin.yaml
      README.md
      ...
  application-backup/
    magpie/
      plugin.yaml
      README.md
      ...
    serverbox/
      plugin.yaml
      README.md
      ...
  backup-storage/
    webdav/
      plugin.yaml
      README.md
      ...
```

The current package folders and validated JSON interface are delivered in 0.3; `RUNTIME-0.3.md` contains the exact layout and starter manifest. The larger tree below remains a design for future archive/script packaging. Current catalog installs copy immutable JSON manifests rather than arbitrary executable archives.

Proposed server layout:

```text
/plugin-catalog/             # read-only available package source, mounted separately
/data/plugins/
  staging/                  # validated installation staging
  packages/<id>/<version>/  # immutable installed package versions
  work/<job-id>/            # per-job temporary execution files
```

The central database records installation status, selected version, checksum and resource references. Directory presence alone does not activate a plugin. Catalog files are never imported/executed by discovery. Plugin-specific instance settings and secret references are stored separately from package contents. Actual secret values remain in server credential storage or deployment mounts.

## Plugin page and visibility

Both clients provide a Plugin page with **可安裝 / 已安裝** views and the four category filters. Cards show name, purpose, author/source, category, version, compatibility and install/update state. A detail view shows supported actions, required configuration, execution location/runtime requirements and declared dependencies.

| State | Plugin page | Service/backup selectors and actions |
| --- | --- | --- |
| Available, not installed | Show `Install` | Excluded |
| Installation in progress | Show progress and output | Excluded |
| Installed and active | Show installed version and lifecycle controls | Available according to capabilities and configuration readiness |
| Installed but disabled | Show disabled state | Excluded; existing resources retain their records |
| Installation failed or incompatible | Show specific error | Excluded |

Successful Install activates that installed version. No first-run registration, recommended-package auto-install or demo auto-install is permitted. Restart preserves explicit installation state. Updating the package catalog does not install or activate its contents.

With no installed service plugin, the service page explains that a service management plugin is required and links to Plugin. Backup setup requires an installed application backup plugin and an installed storage plugin. A storage plugin must also have valid instance configuration before backup execution is available. If an explicit dependency is missing, show it and provide navigation to its Install action; do not silently install it.

The core host list, Plugin page, settings, existing inventory and job history stay accessible. Existing resources referencing unavailable plugins show “尚未安裝所需插件” or the applicable disabled/configuration error, with a Plugin link. Their managed actions are unavailable; records, logs and backups remain preserved.

## Installation and execution

1. The administrator selects Install for an available package. Installing only records/registers the integration and must not run managed-service update/start/stop commands.
2. The server validates package identity, compatibility, declared requirements, checksum and archive paths/size limits, stages the files and atomically records the installed version. Failed installation exposes no partial capabilities.
3. The server publishes capabilities only for active installed plugins. Both clients refresh available types and parameter forms from that server state.
4. The administrator creates a service instance, chooses an installed plugin, selects a host and supplies that instance's configuration.
5. Managed actions are submitted through the existing authenticated job service. Submission binds the operation, plugin ID/version, instance configuration revision and validated parameters. The worker rechecks required availability and permissions before executing. Credentials are resolved centrally.

The generic SSH service plugin supports instance-level command/script definitions for status, start, stop, restart and upgrade, with working directory, timeout and typed parameters. The commands are administrator-authored configuration; action invocation supplies an operation ID and validated values. Parameter binding remains separate from executable shell syntax. SSH quoting/script transfer belongs to the execution layer, with host-key checking enabled. Common service definitions can be exported/imported without writing a new plugin. Named custom-tool targets are halogen service, android-test-env, xpu-mode and zentune. Each gets its own instance definition; dedicated packages are needed only when reusable configuration cannot express its integration. Support declared one-shot or parameterized tool actions as well as service lifecycle operations. An action descriptor supplies a stable ID, label and parameter schema; the server validates it and both clients render it without hard-coding each tool name. Confirm actual tool semantics before defining actions.

OpenCode, OpenChamber, Hermes and ChatGPT each have an application package describing their supported management methods, settings, operations and output parsing. Reuse common execution facilities while preserving independent package identity and installation. Verify upstream instructions and the instance's installation method before selecting commands. Installing an application plugin enables Unified integration; managed-host software installation or upgrade is a separate explicit operation. All application packages require manual Install, including project-published packages.

Custom protocol clients and parsers can be delivered by independently executable plugins. Prefer a structured request/result protocol in a separate runner process over importing package code into the API process. Runner separation is not a sandbox. Plugins requiring extra dependencies or isolation may use their own execution environment, independently of the central Application image. A concrete runtime and dependency-installation policy must be implemented and tested before claiming support for arbitrary executable plugins.

stdout/stderr, progress, structured service status/version and errors have one shared contract. Job locks, log limits, timeouts, interruption recovery and archive validation remain core responsibilities. Demo execution stays explicit and cannot fall back to real SSH/storage/plugin execution.

Upgrade operations run as foreground programs in a centrally owned Shell/PTY session shown inside Job Console. On command success, failure or interruption, the shell remains available for diagnostic commands. Plugins declare the managed upgrade action, execution identity, working directory and interrupt behavior. A trusted runner reports managed command exit through a control channel; terminal text or a visible prompt is not authoritative completion evidence.

The terminal session and managed job have separate lifetimes. A completed job's status and log are immutable; subsequent shell traffic stays in a separate, transient session buffer. The terminal session manager retains the PTY after the worker records completion and releases the managed target lock. Manual shell commands use the SSH account's permissions and are not serialized by managed-job locks. Both clients identify the target, account, foreground program and shell state. PTY output is labeled as merged terminal output.

Console dismissal or connection loss leaves the central session alive within its timeout. Reconnection attaches to the same live session without replaying input or restarting the upgrade. The upgrade timeout and the subsequent shell idle timeout are independent. Reject stale generations and closed sessions, but allow input to a live shell after its associated job ends. Explicit exit/session termination closes the shell; executor restart invalidates the session. Do not persist raw input or diagnostic shell output by default. Sensitive interaction requires remote echo handling. A separate SSH session remains available for parallel diagnostics.

## Updates, disabling and retained data

Installed versions are immutable. An update installs a new version and atomically changes the active version for future submissions. Running jobs continue with their bound version and configuration; old versions remain while referenced by active work. Queued jobs follow the documented availability policy and never silently switch to a different version.

Disabling a plugin removes it from new-instance selectors and stops new managed submissions. Removal must report resource/dependency references and active jobs, and must not delete services, history, backups or configuration as a side effect. Preserve a previous installed version for explicit rollback. Retention/garbage collection is outside the initial lifecycle scope.

## Transition from 0.2.0

Existing inventory, historical jobs and backup catalogs are preserved. Resolve their required plugin IDs for display and migration, but do not auto-install packages to satisfy those references. The administrator installs the corresponding published package through Plugin before those resource actions become available.

The existing capability-driven forms, queue, log persistence and common backup validation are reusable. Replace the image composition root as the activation authority with persisted installation state. Separate available catalog discovery from installed capability discovery. Document database changes, backup and rollback before applying a migration.

## Acceptance

- A fresh real or demo installation reports zero installed plugins and no selectable integrations.
- Publishing/copying a package into the available catalog exposes its Install card only; no code or managed command runs during discovery.
- Install from Web is reflected in Android and vice versa. All lifecycle operations have equivalent capabilities on both clients.
- Interactive upgrade fixtures cover streaming output, prompt response through the same process, interruption, reattachment, return to shell after command exit, immutable final job results and logs, closed-session input rejection, PTY behavior and sensitive input handling in both clients.
- Installing Docker Compose makes its service form/actions appear without rebuilding or restarting the central application.
- A second independent service plugin and its parameters appear without editing backend registration code or rebuilding either client.
- The available catalog includes the required OpenCode, OpenChamber, Hermes and ChatGPT packages; each remains absent from service selectors until explicitly installed. Validate each package's declared operations with fixtures for its supported installation methods, and show the same configuration and capabilities on Web and Android.
- Configure a new tool through an installed generic service plugin, including a declared parameterized action, and run it from both clients with Job Console output without rebuilding the core or clients. Include the four named custom tools in coverage tracking.
- Installing an application backup plugin alone does not enable backup execution without an installed/configured storage plugin.
- Incompatible, corrupt or interrupted installs leave no usable partial integration and return an actionable error.
- Updating a plugin leaves active jobs on their bound version; disabling/removing it preserves dependent records and history.
- Restart retains explicit installation state. Demo isolation and real-mode safety tests continue to pass.
- Migrating 0.2.0 preserves data while requiring explicit installation for referenced integrations.

These are full target acceptance requirements. Delivered 0.3 coverage and remaining boundaries are recorded in `VALIDATION-0.3.md` and `RUNTIME-0.3.md`.


完整的下一版流程、运行边界与实现顺序见 [DESIGN-NEXT.md](DESIGN-NEXT.md)。HTML Review 位于 `prototype/next/`，不代表原生 Android 或正式 API 已交付。

受管套件与宿主插件的身份、能力和依赖规则见 [MANAGED-RESOURCES.md](MANAGED-RESOURCES.md)。安装 Unified 管理插件、登记受管对象、安装远端包是三个独立步骤。
