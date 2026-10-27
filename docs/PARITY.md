# Web / native Android parity · 0.4

Application image 0.4.3 prepares writable directories through its built-in entrypoint. API, schema, authentication and Web/Android operations are unchanged; both clients are 0.4.3.

Both clients use the same central API; no commands run on the client. Themes remain local preferences.

Web and Android 0.3.2 use the selected circular-node U brand. Web shows it in desktop/mobile headers and browser icons; Android shows it in the header and adaptive launcher icon, with a silhouette for themed launchers. Plugin authoring requires Application 0.4.0 and both clients 0.4.0.

The 2026-10-27 npm 12 resolution fix applies centrally to both clients. No client update or new operation is required; real-host evidence is recorded in `scripts/verify-local.py` with an operator-provided private target plan.

| Capability | Web | Native Android | Central ownership |
|---|---|---|---|
| Hosts, service/package/extension/tool overview and filters | Yes | Yes | snapshot/resources |
| Catalog category/install-state filters | Yes | Yes | plugin catalog |
| Create command plugin with operations and custom parameters | Yes | Yes | interface v1 validation |
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
