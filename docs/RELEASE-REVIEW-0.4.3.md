# Release review · 0.4.3

Review date: 2026-10-27. Scope: the first public source snapshot and linux/amd64 Application/Web images. The local repository had no commits when this review started. The initial commit introduces the complete reviewed snapshot; publication checks scan every reachable commit, including any subsequent release fixes.

## Security changes

- Backup packing now opens source files relative to pinned directory descriptors, rejects symlinks, special files and concurrent replacement, and enforces limits on actual bytes read. Seven deterministic regression cases cover file/directory swaps, a replaced source root, file growth, FIFO replacement, excessive entries and directory depth.
- Nginx sends `Content-Security-Policy: frame-ancestors 'none'` and `X-Frame-Options: DENY` on successful and error responses to prevent the management UI from being embedded by another site.
- Both runtime base images are pinned by digest. The Application uses Python 3.12 on Alpine with the full `setpriv` package; runtime installation tooling is removed after installing locked dependencies. The unpublished test image bootstraps its own tooling. Web uses the maintained Nginx Alpine image with package security updates applied.
- Published source excludes local credentials, runtime data, SSH material, distribution archives, screenshots and real-host validation records. Examples use documentation addresses, and first-run Android credentials are empty. Existing saved connections are preserved.

The reviewed boundary is a single trusted administrator. Installed command recipes and SSH sessions intentionally have the authority of the configured remote account. SSH host-key verification, TLS validation, explicit plugin installation, durable job locking, mode isolation and restore validation remain enforced.

## Verification

| Check | Result |
|---|---|
| Backend fixture suite | 80 passed; one existing Starlette/httpx deprecation warning |
| Web integration/unit suite | 14 passed |
| Native Android JVM/Compose suite | 34 passed; debug APK built |
| Container entrypoint | UID/GID 10001, exact argument forwarding, explicit non-root override, fail-closed initialization |
| Isolated Compose acceptance | Fresh directory setup, zero server capability sets, no-new-privileges, read-only SSH, authentication, zero activated plugins, persistence after recreation and graceful shutdown |
| Source and Git history secrets | Gitleaks plus publication-input checks; reviewed initial snapshot and every commit before push |
| Every image layer, configuration and OCI metadata | Gitleaks passed; provenance payloads and tar header metadata included; private deployment markers absent |
| Runtime dependency vulnerabilities | Trivy: 0 findings at all severities in both local candidates |
| Binary asset provenance | Gradle wrapper checked against its official checksum; brand PNGs have no text/EXIF metadata |

Gitleaks 8.30.1 and Trivy 0.76.1 were downloaded from their official releases with pinned SHA-256 verification. `scripts/install-audit-tools.sh` records those checksums. The Gitleaks image scan initially identified two occurrences of the official Python **public signing-key fingerprint** as generic API keys. `.gitleaks.toml` allows only that exact fingerprint in exported image configuration; it does not exclude source files or layers. Positive and negative fixtures in `scripts/test-audit-config.py` verify that source occurrences, other values and additional findings in the same configuration remain detected. Its public origin is documented in the [official Python Dockerfile](https://github.com/docker-library/python/blob/master/3.12/alpine3.23/Dockerfile).

Local candidate image IDs reviewed before the registry build:

- Application: `sha256:3cf94638342747c03e58d13b32d946c724e6818a615958750ae6d2c7ea8c0e0f`
- Web: `sha256:a104f820c410cf690fe58b054181fbb4ef75ec0913a8abd0146927f117813d61`

The publication workflow builds from the exact reviewed commit and adds source/revision/version labels. It repeats the source/history, regression, container, all-layer secret and High/Critical vulnerability gates before pushing. The registry digests in the workflow summary identify those published builds; they differ from local candidates because of release metadata and build timestamps. Version tags are immutable by workflow policy.

`scripts/test-image-audit.py` supplies an OCI archive with a detector fixture present only in its provenance. The gate verifies that the exporter preserves that payload and that Gitleaks detects it. Image export also retains index/manifests, other archive payloads and layer header owner/PAX metadata.

## Limits and follow-up

These results describe the reviewed content and advisory databases at the time of checking. They are not a guarantee against undiscovered defects or future advisories. No production NAS deployment, real-host operation, live WebDAV restore, or physical-device Android acceptance was performed for this release gate. Those require a separate authorized target and acceptance record. The debug APK is a development build; production signing remains a separate task.

Use the [OMV Compose guide](OMV-COMPOSE.md) for deployment. Keep existing data paths and project identity when upgrading. Review every future commit and image publication under [SECURITY.md](../SECURITY.md).
