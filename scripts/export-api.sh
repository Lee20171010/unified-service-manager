#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker run --rm -e UNIFIED_MODE=demo -e ADMIN_TOKEN=unified-demo-token-local-only-2026 unified-application python -c 'import json; from unified.api import create_app; print(json.dumps(create_app().openapi(),ensure_ascii=False,indent=2))' > docs/openapi.json
