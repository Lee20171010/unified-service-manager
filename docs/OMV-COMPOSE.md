# Docker / OMV Compose deployment · 0.4.3

The release uses two images: `ghcr.io/lee20171010/unified-application:0.4.3` and `ghcr.io/lee20171010/unified-web:0.4.3`. Public images can be pulled without registry login. The current image platform is linux/amd64.

## OMV setup

In Services → Compose → Files, create `unified` or edit the existing project. Paste [compose.yaml](../deploy/omv/compose.yaml) into **File** and the following into **Environment**:

```dotenv
ADMIN_TOKEN=replace-with-a-unique-random-token-of-at-least-32-characters
BIND_ADDRESS=127.0.0.1
PORT=4180
WEBDAV_URL=
WEBDAV_USER=
WEBDAV_PASSWORD=
```

Generate a token with `openssl rand -hex 32`, or retain the existing token when updating. Save and select **Up**; Docker pulls missing images. No image build, tar download, manual mkdir/chown or separate initialization service is required.

Relative mounts resolve beside the Compose file. Select the desired data disk in OMV's Compose settings before initial deployment.

| Mount | Content |
|---|---|
| `./data:/data` | Database, inventory, jobs/logs, plugin imports/installations and archive cache |
| `./ssh:/run/ssh:ro` | Dedicated SSH keys and verified known_hosts |
| `./sources:/sources` | Application configuration snapshot sources and restore targets |
| `plugin-catalog:/plugin-catalog:ro` | Available plugin definitions in a persistent named volume |

The entrypoint prepares root-owned empty data/source directories and execs the server as 10001:10001 with no capabilities. Existing nonempty directories and other owners are preserved. SSH contents are never modified; keys must be readable by UID 10001, with suitably restricted permissions. With an explicit non-root Docker `user`, initialization is skipped and mounts must already be writable.

## Access

The Web service listens on NAS loopback port 4180. Use your HTTPS reverse proxy. If Tailscale runs on the NAS host, inspect `tailscale serve status`, then configure an unused HTTPS port, for example:

```bash
tailscale serve --bg --https=9443 http://127.0.0.1:4180
```

Use your own hostname and chosen port in both Web and Android, with the same administrator token. If Tailscale runs in a separate bridge container, configure its network path to Web instead of using the host's loopback address.

After connecting, install desired plugins and register your hosts/resources. The 13 available plugin definitions are not installed automatically. Register host addresses, SSH accounts and key file references; independently verify SSH host fingerprints.

## Updates and existing installations

Keep the same Compose project name, environment values and host mount paths. If existing data uses an absolute path, retain it instead of switching to an empty relative directory. Update the component image versions, then **Pull / Up**. With the CLI, use `docker compose pull` followed by `docker compose up -d`.

Earlier offline images remain usable under their existing tags. The first registry release contains security/privacy changes and must be pulled; changing an old tag does not apply those changes. Application 0.4.2 or newer initializes storage inside its entrypoint. Remove any earlier storage-init service/dependency and application cap_drop setting when adopting this Compose. An obsolete stopped storage-init container can be removed separately without deleting volumes.

Saved application data survives ordinary Up/Down and container recreation. Do not select volume deletion for routine updates. Manual edits outside mounted paths belong to the container layer and do not survive recreation. Changing the schema in future releases requires an explicit compatibility review; no new manager backup/migration feature is included in this release.

## Release maintenance

Review every commit and image before publishing as described in SECURITY.md and AGENTS.md. Build/test from the reviewed commit; the manual publication workflow records image digests and links images to the source repository. Numeric release tags identify immutable contents.

Local deployment tests use disposable directories and no remote hosts: `python3 scripts/test-entrypoint.py` and `python3 scripts/test-omv.py`. See [startup validation](VALIDATION-ENTRYPOINT.md) for the runtime contract.
