# Release review · 0.4.5

Scope: public main-branch ancestry, service plugin defaults, Android diagnostic export and forms, and linux/amd64 Application/Web images. The release keeps schema/API v1 and requires explicit installation/update of each plugin. Managed hosts and the user's NAS are outside this release's execution tests.

## Reviewed changes

- Security review found a legacy submission race with plugin updates. Application.submit now uses the same RLock as plugin lifecycle changes, covering the binding and persistence boundary. A deterministic regression fails on the original implementation (recorded 1.0.0, executed 1.1.0) and passes after the fix, proving the recorded plugin version matches the worker-executed version.

- Four independently installable v1.1.0 command plugins provide Linux/systemd state, version, lifecycle, upgrade and environment checks. Parameters are shell-quoted environment assignments; executable operations use argv lists. An exact existing unit is required. Updater failure stops the recipe, and successful updates restart only the selected unit if it was running. Upstream package installation scripts retain their own behavior.
- Existing instance commands take precedence over defaults; missing newly added fields use manifest defaults. Both clients retain hidden override values. Exact unused factory templates are retired without removing installed or administrator-imported definitions. billion-context retains its stable ID.
- Native diagnostics retain bounded local event names, exception classes and code frames. They omit URLs, token values, exception messages, response bodies and source filenames. Storage is backup-excluded; export/share are explicit user actions. Crash recording preserves the original handler. The APK is a development/debug build.
- The release workflow binds builds to the exact reviewed commit and version, checks its full public ancestry, and refuses to overwrite numeric image tags. Both numeric images must be pushed before latest aliases are promoted. The aliases move separately; publication completion is confirmed only after both match their numeric release digests.
- OMV Compose uses IMAGE_TAG, default latest, with explicit pulling. Data, SSH, source and catalog mount paths are preserved. Offline packages instead pin the numeric version and disable registry pulling.

## Verification

| Check | Evidence |
| --- | --- |
| Backend fixtures | 96 passed; one existing Starlette/httpx deprecation warning |
| Web tests | 15 passed |
| Android JVM/Compose tests | 44 passed; 0.4.5 debug APK built, versionCode 13 |
| Service recipes | Isolated fake executables; six operations for four recipes, failure and stopped-state preservation, precise target, parameter quoting and legacy override compatibility |
| Container entrypoint and OMV stack | Non-root server UID/GID 10001, zero capability sets, read-only SSH, authentication, explicit plugin activation, directory initialization, recreation persistence and graceful shutdown |
| Image secrets/privacy | All filesystem layers, archive headers, configuration, history and OCI payloads inspected; Gitleaks and private deployment-marker checks found no matches |
| Runtime vulnerabilities | Local candidate images: zero Trivy findings at every severity in the advisory database checked on 2026-10-27 |
| APK | Signature verification, manifest and extracted executable strings scanned; no secret/private-deployment-marker matches |
| Audit tools | Gitleaks 8.30.1, Trivy 0.76.1; audit allowlist and image exporter positive/negative fixtures passed |

Local image candidates reviewed before the commit-bound registry build:

- Application: `sha256:8f39a230cd37bc63d0ba851270f964efa08765ee6389adb1f5645e98c65e2163`
- Web: `sha256:f498b9136bb1dfa27fe0a32e325da6e8ac147bfad16f4a445229550713923566`
- Android APK SHA-256: `9477faab9c7625a288c655e7915166da53ba5747a2b29321626ab3e5af66f248`

The publication workflow repeats source/history, regression, initialization, all-layer secret and High/Critical vulnerability gates on its exact commit-bound builds. Its output and the GitHub release's release-evidence.json identify the reviewed commit, workflow run, published digests and artifact checksums. Registry builds differ from local candidates due to their revision labels and build metadata. A separate Astra/max review covers the security/privacy boundary and the staged change before commit/push.

Public-history review includes every commit reachable from the release tip. Unrelated local working snapshots are excluded from both the public graph and push refspecs. Published artifacts contain only the APK, reusable plugin definitions, deployment templates, usage notes and review evidence; no local logs, runtime configuration or credentials are included.

## Limits and deployment

The new Android dialog tests use the documented 320dp Robolectric measurement workaround; wide-window/device acceptance is separate. Earlier diagnostic connection/crash tests ran on an isolated emulator package. No real service upgrade, NAS deployment, production WebDAV restore or new physical-device acceptance is claimed by this release gate.

A clean scan is evidence about the reviewed artifacts and current advisory database, not a guarantee against future vulnerabilities. Read [SECURITY.md](../SECURITY.md), [OMV-COMPOSE.md](OMV-COMPOSE.md) and [PLUGIN-CATALOG.md](PLUGIN-CATALOG.md) before deployment. Existing catalog volumes retain their definitions: import new plugin JSON and explicitly Update after the core update.
