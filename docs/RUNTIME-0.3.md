# Unified runtime and operations

0.3 delivers installation-controlled plugins, managed packages/tools, host bindings and interactive job input in the central Application Layer, Web and native Android. The independent HTML reference remains under `prototype/next/`.

## Start using it

1. Connect both clients to the same Application Layer. The local review instance at <https://manager.example.com/> is **demo**. It persists shared state but never contacts managed hosts. APK downloads: <https://manager.example.com/>.
2. Open **插件** and Install a management integration. Fresh instances and upgraded 0.2 databases have zero installed plugins. Installing a management plugin only activates server capabilities.
3. Add a host. In SSH mode its account, private-key filename and verified `known_hosts` come from the deployment mount. Add a managed resource using an installed integration. Registering the object does not install remote software.
4. For npm/CLI resources, supply the package name, user prefix or project directory, absolute Node path, absolute `npm-cli.js` path and `latest` or an exact version. Example paths depend on the remote Node installation; nvm installations need their own paths. The SSH account owns the installation. `latest` is resolved on the target before job submission, then the exact version is retained on the job.
5. Choose **安裝套件**, **更新**, **卸載套件**, **重新整理狀態** or **檢查執行環境**. Node/npm must already be installed on that host. The environment check currently verifies the selected Node executable and package observation; it does not inspect OAuth accounts.
6. Open Job Console for output and input. Dismissing it detaches the UI. The server keeps the process/session until completion, explicit session close, connection failure or timeout. Reopen the job to attach again. Input has generation/sequence checks and is never automatically retried.

The review demo deliberately simulates programs. Real mode executes SSH commands with host-key verification. Never point the demo database at real mode: the mode identity check rejects it.

## Available integrations

11 independently versioned JSON package folders are supplied under `plugins/<category>/<id>/`:

- Service management: `compose`, `opencode`, `openchamber`, `hermes`, `chatgpt`.
- Package management: `npm-packages`, `billion-context`, `oc-codex-multi-auth`.
- Application backup: `magpie`, `serverbox`.
- Backup storage: `webdav`.

Named service plugins ship Linux/systemd defaults with per-instance command overrides. See [the catalog guide](PLUGIN-CATALOG.md) for the supported installation paths and upgrade behavior. Service and tool are authoring choices; create a concrete plugin from the Plugin page. Additional manifest fields become `UNIFIED_<UPPERCASE_FIELD>` environment variables.

A status recipe can print `active`, `running`, `online`, `inactive`, `stopped`, `failed`, or JSON such as `{"status":"online","version":"1.2.3"}`. Other output gives unknown status. Ensure the observation recipe exits successfully for valid stopped states (for example, `systemctl is-active my-unit || true`). Command exit success alone does not prove the service is running.

The npm integrations manage explicit user-prefix and project installations. The dedicated billion-context/auth packages fix the npm package identity and declare compatible hosts. They do not take ownership of pre-existing OpenCode-managed caches or run upstream account commands. Register that actual installation layout only after checking it; this release supports npm-owned scopes, not every application's private cache format. `billion-context` requires Node 20+; current `oc-codex-multi-auth` requires Node 22.19+. Check the installed package's own engine requirements when choosing a version.

## Host bindings

A package can be associated with compatible services on the same host/account. billion-context permits OpenCode and Hermes; oc-codex-multi-auth permits OpenCode. Association is a stored record. Register/unregister are separate jobs using explicitly saved administrator recipes. Recipes receive `UNIFIED_PACKAGE`, `UNIFIED_DIRECTORY`, and `UNIFIED_VERSION`; use the upstream integration procedure for the actual application version. OAuth pools and credentials are outside these forms.

A successful registration recipe records registration intent. Installed package version and observed loaded version remain separate. Upgrade marks registered hosts as needing restart/check, and does not restart them. Restarting a host invalidates its loaded observation; it does not invent a loaded version. A separate saved probe must output an exact version, `none` (not loaded), or `unknown`. Uninstall is rejected while a relation is registered, still loaded, or unknown. To unload: unregister, restart/stop as appropriate, then run the probe. Re-associating the same host updates its recipes without discarding relation state.

Package jobs lock their installation identity and associated hosts. Related service operations conflict. Editing settings and plugin lifecycle changes are rejected while relevant work is active. Existing bindings, resources, logs and backups remain when a management plugin is disabled/removed. Editing a resource preserves installation identity; change host/account/location by registering another resource.

## Package authoring without a core rebuild

0.4 adds Web/Android creation, JSON file or pasted import, validation preview and export. See [PLUGIN-AUTHORING.md](PLUGIN-AUTHORING.md). UI documents persist under `/data/plugins/catalog/<id>/plugin.json`, take precedence over supplied catalog entries, and still require explicit Install/Update. The following interface v1 format remains current.

Current distribution uses the 0.5 source contract in PLUGIN-CATALOG.md: generic definitions are image-bundled, specific packages are fetched from GitHub on explicit install/update, and user imports persist under data. Legacy /plugin-catalog mounts remain a compatibility source for modified documents. Install copies a validated canonical manifest into /data/plugins/packages/<id>/<version>/plugin.json and commits its checksum/activation record. Installed content is immutable; updates retain previous versions for explicit rollback. The busy-job check and final activation share Application's lock, while network downloads run outside that lock. In-flight operations never hot-swap their plugin implementation.

Interface v1 supports reusable `commands` and `npm` execution drivers plus the existing Compose and backup primitives. A new command integration can declare fields and fixed operation IDs without backend registration edits or client rebuilds. Arbitrary central Python imports, custom runner binaries, package archives and dependency resolution are not part of this runtime interface. Unsupported drivers/interfaces/dependencies fail validation. Catalog filesystem access is administrator-controlled; command recipes run with the selected SSH account's permissions.

Minimal command plugin:

```json
{
  "id": "my-tool", "version": "1.0.0", "interface_version": 1,
  "label": "My tool", "category": "service-management",
  "driver": "commands", "resource_kind": "tool", "operations": ["run"],
  "fields": [
    {"name": "directory", "label": "Working directory", "initial": "/opt/tools"},
    {"name": "identity", "label": "Instance identity", "initial": "my-tool"},
    {"name": "arguments", "label": "Argument", "required": false, "initial": ""}
  ],
  "commands": {"run": "./my-tool --mode \"$UNIFIED_ARGUMENTS\""}
}
```

## Job console and shell lifetime

Managed commands use an SSH exec PTY, with stdout/stderr labelled as merged output in durable logs. The SSH channel's exit status is authoritative. After that program exits, a **new diagnostic shell on the same SSH connection** is opened in the same Console. It does not inherit the program's changed directory/environment; the UI identifies this transition. Preserving the exact original shell process is a further terminal refinement, not a claimed capability of 0.3.

The diagnostic buffer stays in memory, separate from immutable managed-job logs. Raw input is not stored; remote PTY echo still follows the remote program. A shell expires after 15 minutes of input inactivity. Maximum 16 live real job sessions. Executor restart closes all sessions, marks active jobs uncertain/failed and does not replay operations. The separate host SSH terminal remains available; it ends on disconnect. Backup jobs have logs and do not open shells.

## Upgrade, rollback and validation

The schema remains v1: new plugin records use the existing entities table; resources retain existing service IDs and add JSON fields. `/snapshot.resources` includes all object kinds; `/snapshot.services` remains the service subset for older clients. `/services` rejects creating package/tool objects. Both current clients use `/resources`.

Before rollout, use SQLite's backup API to copy the database and retain the previous application/web images. Keep real and demo volumes distinct. Rebuild the core once for 0.3 and install the new APK. Subsequent supported plugin/recipe updates require no core/client rebuild. Restoring the pre-upgrade database plus old images is the supported rollback; do not run 0.2 against a database containing new resource kinds. See `DEPLOYMENT.md` for the baseline SSH/WebDAV mounts.

Validation evidence lives in `VALIDATION-0.3.md`. Fixture success is distinct from real NAS installation and Android physical-device acceptance.
