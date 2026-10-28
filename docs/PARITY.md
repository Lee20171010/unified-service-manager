# Web / native Android parity · 0.4

Application/Web/Android 0.6.1 retain API/schema v1. Both clients create Compose/npm/command plugins and copy existing manifests, alongside central GitHub catalog refresh, verified downloads and persistent custom definitions. Both clients use the same installed plugin descriptors and managed operations.

Both clients use the same central API; no commands run on the client. Themes remain local preferences.

Web and Android 0.3.2 use the selected circular-node U brand. Web shows it in desktop/mobile headers and browser icons; Android shows it in the header and adaptive launcher icon, with a silhouette for themed launchers. Plugin authoring requires Application 0.4.0 and both clients 0.4.0.

The 2026-10-27 npm 12 resolution fix applies centrally to both clients. No client update or new operation is required; real-host evidence is recorded in `scripts/verify-local.py` with an operator-provided private target plan.

| Capability | Web | Native Android | Central ownership |
|---|---|---|---|
| Hosts, service/package/extension/tool overview and filters | Yes | Yes | snapshot/resources |
| Catalog category/install-state filters | Yes | Yes | plugin catalog |
| Create service/package/extension/tool plugin; Compose/npm/custom commands | Yes | Yes | interface v1 validation |
| Copy existing Compose/npm/command plugin to a new ID with full JSON editing | Yes | Yes | manifest export, preview and import |
| Import JSON file / paste, preview, save to available catalog | Yes | Yes | atomic persistent document import |
| Export available plugin JSON | Download | Android document picker | clean manifest export |
| Install/update/enable/disable/remove/rollback plugins | Yes | Yes | plugin lifecycle |
| Descriptor-based resource forms and edit settings | Yes | Yes | validation, identity |
| Service lifecycle / configured tool Run | Yes | Yes | job worker |
| npm check/install/update/uninstall/environment check | Yes | Yes | SSH runner, fixed version |
| Associate/edit host recipes | Yes | Yes | resource bindings |
| Register/unregister/probe loaded version | Yes | Yes | binding jobs |
| Installed vs loaded version / restart-needed state | Yes | Yes | independent observations |
| Job history, output, errors, complete log download/export | Yes | Yes | durable logs |
| Job input, Ctrl+C, explicit end, close/reopen Console | Yes | Yes | central session generation/sequence |
| Transient diagnostic shell after managed command | Yes | Yes | separate SSH shell on same connection |
| Independent host SSH terminal | Yes | Yes | Terminal Gateway |
| Magpie/ServerBox WebDAV backup and guarded restore | Yes | Yes | shared backup policy |
| Server-name entry → address/status details → edit connection | Yes, current origin | Yes, saved URL | existing authentication |
| Automatically connect saved workspace on launch | Yes, same origin | Yes, saved URL/Keystore token | authenticated snapshot |
| Foreground refresh and temporary network recovery | Yes | Yes | read-only polling; no operation replay |
| Light/dark/system | Yes | Yes | client preference |

Real command execution has isolated SSH fixture coverage. Android has local Compose/Robolectric tests and a built APK; this is not physical-device certification. Review deployment uses demo. Exact implementation limits and configuration examples are in `RUNTIME-0.3.md`; results are in `VALIDATION-0.3.md`.

Client 0.4.1 adds automatic connection and lifecycle recovery using Application 0.4.0. Android first launch still requires explicit configuration; restored processes reconnect without relying on cached credentials in RAM. Inventory/jobs are fetched from the server, while a surviving Activity/ViewModel retains navigation and selected console. System-restored UI uses rememberSaveable keyed by workspace URL; force-stopping/relaunching is not a guarantee of restoring every open dialog. Independent SSH shell connections and expired central sessions are not recreated automatically.

Public release 0.4.3 removes private deployment defaults from both clients and examples. Android first-run fields are empty; previously saved connections are retained. Central backup hardening applies equally to both clients.

## Plugin defaults · 0.4.5

Four service packages v1.1.0 provide Linux/systemd refresh, start, stop, restart, upgrade and doctor operations through existing descriptors. Web and Android use the same operations and fields; optional instance command overrides are under advanced settings and retain their values when collapsed. Nonempty instance commands take precedence over manifest commands; missing newly added settings receive manifest defaults. No new endpoint or schema version is introduced. See [PLUGIN-CATALOG.md](PLUGIN-CATALOG.md) for supported environments, legacy-template preservation and updates through JSON import. Android 0.4.5 carries the new form layout; Application 0.4.5 supplies the override/default semantics.

Android 0.4.6 fixes main-thread TLS cleanup after temporary connection errors and during disposal. Shared managed operations and Web behavior are unchanged; Android reconnects after a transient 502 without changing saved credentials. Docker images remain 0.4.5.

## GitHub catalog · 0.5.0

Both clients display builtin/GitHub/custom/installed provenance, latest available and installed versions, cached catalog state and refresh errors. Both provide Check plugin updates through the authenticated central endpoint, and pin displayed version/checksum on Install/Update. Application alone downloads and validates packages. User imports override official entries; installed versions continue offline. Metadata refresh does not activate or execute plugins. API/schema remain v1.

## Android foldable layout · 0.5.1

Android adapts bottom navigation/rail and host/resource list-detail panes to window size. Both clients retain the same actions, validation and central execution. Android preserves navigation through resizing and keeps connection/form/console drafts in ViewModel-owned memory through Activity recreation. Process death discards those drafts; it does not replay an action. Application/Web remain 0.5.0 and API/schema v1; no Compose or environment changes are needed.

## Personal plugin authoring · 0.6.0

Both clients offer equivalent resource-kind and management-method choices, npm scope/runtime/version fields, extension host IDs and full-manifest copying. Save only updates the available catalog; explicit Install activates capabilities. Compose IDs are independent, with shared host/directory locks. Backup application/storage packages retain their dedicated interfaces.

## Host entry and unselected layout · 0.6.1

Both clients require an explicit private-key filename in the new-host form and explain its central SSH mount location. Android shows a full-width list until a detail is selected, then uses list/detail panes when space permits; closing returns to the full-width list. Web retains its existing detail presentation.
