# Unified Service Manager

Manage services, packages and configuration snapshots across multiple hosts from a Web UI or native Android app. Both clients use the same authenticated central application API. Release **0.5.0** separates generic built-in plugins from the official GitHub catalog. Both clients can check available versions and explicitly install or update verified local copies. Custom definitions and installed versions persist across image updates.

## Deploy with Docker Compose

Images are published under:

- `ghcr.io/lee20171010/unified-application:latest`
- `ghcr.io/lee20171010/unified-web:latest`

`latest` tracks the most recent reviewed stable release. Set `IMAGE_TAG=0.5.0` to pin this release. Pulling downloads images; Up recreates containers when needed. Official metadata refreshes at startup and every six hours, with a manual check in both clients. Install/Update downloads the selected package; installed execution content changes only on explicit approval. See [the catalog guide](docs/PLUGIN-CATALOG.md).

Use [deploy/omv/compose.yaml](deploy/omv/compose.yaml) with [env.example](deploy/omv/env.example). This configuration also works with ordinary Docker Compose. Set a unique `ADMIN_TOKEN` of at least 32 characters, then run:

```bash
docker compose pull
docker compose up -d
```

In OMV Compose, paste the YAML into **File**, the environment template into **Environment**, retain your existing token or fill a new one, save and select **Pull**, then **Up**. See [the OMV guide](docs/OMV-COMPOSE.md) for complete steps.

The image prepares fresh writable directories and runs the server as UID/GID 10001. Data lives in `./data`, SSH keys in read-only `./ssh`, and configuration snapshot sources in `./sources`. The `plugin-catalog` named volume is retained for compatibility: modified legacy definitions are copied into `./data` without overwriting UI imports. Generic builtins come from the image at `/builtin-plugins`; GitHub metadata/downloads and installed packages live under `./data/plugins`. Preserve these paths and the Compose project identity during updates.

The Web port binds to `127.0.0.1:4180` by default. Put it behind your HTTPS reverse proxy or Tailscale Serve. Web and Android connect to your own server address using the same administrator token. Android starts with empty connection settings.

## Capabilities

- Multi-host inventory, observed status and dynamic resource registration.
- Explicit plugin install/update/rollback; creating and importing JSON command plugins from either client.
- Service upgrade, start, stop, restart and status; reusable command and npm package integrations.
- Durable background jobs, stdout/stderr, full logs and interactive diagnostic input.
- Independent authenticated SSH sessions with a line-oriented terminal.
- Magpie and Flutter ServerBox configuration snapshots through WebDAV.
- Light, dark and system appearance; automatic restoration of saved connections.

Fresh instances have no plugins installed. Available definitions do not activate functionality until an administrator installs them. See [the concrete plugin catalog and default operations](docs/PLUGIN-CATALOG.md). Read [plugin authoring](docs/PLUGIN-AUTHORING.md) and [runtime capabilities](docs/RUNTIME-0.3.md) before adding recipes.

## Local development and demo

```bash
python3 scripts/configure.py
docker compose -f compose.yaml -f compose.demo.yaml up -d --build
```

Open http://127.0.0.1:4180. Demo mode uses the intentionally public fixture token `unified-demo-token-local-only-2026`, cannot contact real SSH/WebDAV targets, and stores its data separately. Real mode rejects that token.

```bash
bash scripts/test.sh
android/gradlew -p android :app:assembleDebug :app:testDebugUnitTest --max-workers=2
```

Android requires JDK 17/21 and Android SDK 35. Build outputs, local credentials, deployment records and screenshots are excluded from Git. The accepted mock prototype is retained under `prototype/`; production source is `web/`.

## Project guide

| Area | Responsibility |
|---|---|
| `backend/` | Application services, jobs, SQLite, verified SSH and WebDAV |
| `web/` | Browser client and same-origin Nginx proxy |
| `android/` | Native Kotlin / Jetpack Compose client |
| `plugins/` | Categorized plugin manifests, installed explicitly |
| `prototype/` | Mock UI reference |
| `docs/` | Architecture, API, parity, deployment and maintenance |

Read [architecture](docs/ARCHITECTURE.md), [API](docs/API.md), [client parity](docs/PARITY.md), [testing](docs/TESTING.md), [handoff](docs/HANDOFF.md) and [security](SECURITY.md). Builds and fixture verification are separate from acceptance on real devices and infrastructure.
