#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
android/gradlew -p android :app:assembleDebug :app:testDebugUnitTest --max-workers=1
mkdir -p artifacts
cp android/app/build/outputs/apk/debug/app-debug.apk artifacts/unified-0.6.1-debug.apk
cd artifacts
sha256sum unified-0.6.1-debug.apk > unified-0.6.1-debug.apk.sha256
