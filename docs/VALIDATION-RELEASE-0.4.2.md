# Docker release naming · Application 0.4.1 / Web 0.4.2

## Release contract

Component image tags use numeric versions independent of the deployment platform. New image contents require a new component version. `scripts/package-omv.sh` exports existing release images and never rebuilds or replaces a published tag. The combined downloadable bundle is `unified-0.4.2-images-amd64.tar.gz`; Application is 0.4.1, Web/APK are 0.4.2.

This naming migration preserves the already distributed image payload exactly. Application `/info.version` and `/healthz.version` remain the embedded code version 0.4.0; API version is 1. No runtime source, database or client change is included.

## Retag evidence

The following old/new tag pairs were compared using Docker image inspect. Each pair resolves to one identical image ID and shares all layers.

| Previously distributed tag | Current tag | Identical image ID |
|---|---|---|
| unified-application:0.4.0-omv2 | unified-application:0.4.1 | `sha256:3c110c157579e005311528cda58c543b55980a4aafdba0024900ac94d969a915` |
| unified-web:0.4.2-omv1 | unified-web:0.4.2 | `sha256:1f4d6c389e363a69c76e40dd3f4c89c9bf00bbac563ff40ca675de75b0cbdada` |

Users who imported those exact prior tags can retag locally and update Compose without downloading. The older Application 0.4.0-omv1 lacks storage initialization and must not be retagged as this release. Migration and optional old-tag removal are documented in OMV-COMPOSE.md.

## Verification

- Prior image payload gate: 71 backend tests and 14 Web tests passed; recorded in VALIDATION-OMV2.md. No executable payload changed in this naming migration.
- Current Compose uses Application 0.4.1 in both storage-init and application, and Web 0.4.2.
- Isolated Compose acceptance with current tags: **PASS**. Fresh bind initialization, non-root operation, authentication, no activated plugins, import persistence after recreation and existing SSH fixture preservation all passed.
- Artifact verification checks the exported archive contains exactly the two current release tags, that packaging preserves image IDs, and that served Compose/env and image downloads match local SHA-256 values.

No real NAS deployment or service operation was performed. APK remains 0.4.2.
