# Client validation · 0.4.2

Web/native Android 0.4.2 use a compact server-name entry and a server details → edit connection flow. Application remains 0.4.0, with unchanged API, credentials, automatic connection and job behavior.

## Reference and scope

Reviewed the installed OpenChamber web package metadata (2.5.2), its current official mobile connection source and device documentation on 2026-10-27:

- [MobileConnectionWelcome.tsx](https://github.com/openchamber/openchamber/blob/main/packages/ui/src/apps/MobileConnectionWelcome.tsx): saved connections identify servers by label and address; manual connection lives in the connection interface.
- [Connect a Device](https://docs.openchamber.dev/connect-devices/): documents OpenChamber's pairing workflow.

Unified adopts the server-centered presentation for its existing single workspace. The server name comes from the Web origin or Android's saved URL. Tailnet hostnames use their short name in the compact entry; the complete address appears in details. Connection details expose credential editing as a separate action. Routine status chrome is quiet on success; demo and connection failures remain explicit. The existing authentication/transport model is unchanged.

## Evidence

- `scripts/package-android.sh`: native APK 0.4.2, versionCode 10 built; all 33 tests passed. The connection UI regression verifies server details, token field hidden until Edit connection, then form retention until the server accepts a connection. Existing automatic restoration, lifecycle, stale-response, no-replayed-write and plugin tests pass.
- `node --check web/app.js` and `node --test tests/*.test.cjs`: syntax check and 14 tests passed.
- Browser on local demo: reload automatically connects; one server-name entry opens full address/status; Edit connection reveals the masked token form. Closing the form preserves the connected workspace.
- 390×844 browser viewport: page scrollWidth 375, server entry about 90 px wide, no horizontal overflow, connection notice hidden while connected.
- Screenshots: `preview/server-connection-0.4.2-desktop.png` and `preview/server-connection-0.4.2-mobile.png`.
- Review Web deployed on the review host; prior Web image retained as `unified-web:before-0.4.2`. Application was not restarted. nas-host deployment and Android physical-device acceptance remain separate from this local/browser evidence.
