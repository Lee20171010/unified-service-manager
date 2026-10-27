#!/usr/bin/env bash
# Export immutable component image releases for Docker / OMV Compose.
set -euo pipefail
cd "$(dirname "$0")/.."
version=$(python3 scripts/release-version.py)
release=unified-application-${version}-web-${version}-amd64
images=unified-application-${version}-web-${version}-images-amd64.tar.gz
web_image=unified-web-${version}-amd64.tar.gz
application_image=unified-application-${version}-amd64.tar.gz
stage=$(mktemp -d /tmp/unified-omv-package.XXXXXXXX)
trap 'rm -rf -- "$stage"' EXIT
mkdir -p "$stage/$release" artifacts
# Export the exact release images. Build/tag a new version before invoking this
# script; packaging must never silently replace an already published image.
docker image inspect ghcr.io/lee20171010/unified-application:${version} ghcr.io/lee20171010/unified-web:${version} >/dev/null
docker image save ghcr.io/lee20171010/unified-application:${version} ghcr.io/lee20171010/unified-web:${version} | gzip -1 > "$stage/$release/images.tar.gz"
docker image save ghcr.io/lee20171010/unified-web:${version} | gzip -1 > "$stage/$web_image"
docker image save ghcr.io/lee20171010/unified-application:${version} | gzip -1 > "$stage/$application_image"
cp deploy/omv/compose.yaml deploy/omv/env.example "$stage/$release/"
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$version/" "$stage/$release/env.example"
sed -i "s/pull_policy: always/pull_policy: never/" "$stage/$release/compose.yaml"
cp docs/OMV-COMPOSE.md "$stage/$release/README.md"
cp docs/OMV-COMPOSE.md docs/DEPLOYMENT.md docs/RUNTIME-0.3.md docs/RELEASE-REVIEW-${version}.md docs/VALIDATION-ENTRYPOINT.md docs/PLUGIN-AUTHORING.md "$stage/$release/"
docker image inspect ghcr.io/lee20171010/unified-application:${version} ghcr.io/lee20171010/unified-web:${version} \
  --format '{{json .RepoTags}} {{.Id}} {{.Os}}/{{.Architecture}}' > "$stage/$release/images.txt"
(cd "$stage/$release" && sha256sum images.tar.gz > images.tar.gz.sha256)
tar -czf "$stage/$release.tar.gz" -C "$stage" "$release"
mv "$stage/$release.tar.gz" "artifacts/$release.tar.gz"
mv "$stage/$release/images.tar.gz" "artifacts/$images"
mv "$stage/$web_image" "artifacts/$web_image"
mv "$stage/$application_image" "artifacts/$application_image"
(cd artifacts && sha256sum "$release.tar.gz" > "$release.tar.gz.sha256")
(cd artifacts && sha256sum "$images" > "$images.sha256" && sha256sum "$web_image" > "$web_image.sha256" && sha256sum "$application_image" > "$application_image.sha256")
cp "$stage/$release/compose.yaml" "artifacts/$release.compose.yaml"
cp "$stage/$release/env.example" "artifacts/$release.env.example"
cp deploy/omv/compose.yaml artifacts/unified-omv-compose.yaml
cp deploy/omv/env.example artifacts/unified-omv.env.example
echo "Ready: artifacts/$release.tar.gz, checksum, Compose and env template"
