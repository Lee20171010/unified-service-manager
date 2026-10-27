#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -f backend/Dockerfile -t unified-application .
docker build -f backend/Dockerfile.test -t unified-tests .
docker run --rm unified-tests
node --check web/app.js
node --check web/api.js
node --check web/theme.js
node --check web/capabilities.js
node --check web/plugin-editor.js
node --test tests/*.test.cjs
