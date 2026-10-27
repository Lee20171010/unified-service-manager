#!/usr/bin/env bash
# Shared-device acceptance with synthetic state and an isolated application ID.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${ANDROID_TEST_ADB_WRAPPER:?Set the configured ADB wrapper}"
: "${ANDROID_TEST_SESSION_WRAPPER:?Set the configured session-lock wrapper}"
: "${ANDROID_HOME:?Set the Android SDK directory}"

if [[ ${1:-} != --device-session ]]; then
  android/gradlew -p android -PisolatedDeviceTest=true \
    :app:assembleDebug :app:assembleDebugAndroidTest --max-workers=1
  exec "$ANDROID_TEST_SESSION_WRAPPER" bash "$0" --device-session
fi

package=dev.unified.app.acceptance
app=android/app/build/outputs/apk/debug/app-debug.apk
test_app=android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
aapt="$ANDROID_HOME/build-tools/35.0.0/aapt"
report=.local/android-device-tests
mkdir -p "$report"

check_package() {
  local actual
  actual=$("$aapt" dump badging "$1" | sed -n "s/^package: name='\([^']*\)'.*/\1/p")
  [[ "$actual" == "$2" ]] || { echo "Refusing APK with unexpected package: $actual"; exit 1; }
}
check_package "$app" "$package"
check_package "$test_app" "$package.test"

adb() { timeout 300 "$ANDROID_TEST_ADB_WRAPPER" "$@"; }
adb devices -l > "$report/devices.txt"
[[ $(awk '$2 == "device" {n++} END {print n+0}' "$report/devices.txt") == 1 ]] || {
  echo "Exactly one configured test device must be available."
  exit 1
}
for candidate in "$package" "$package.test"; do
  installed=$(adb shell pm list packages "$candidate")
  if [[ "$installed" == *package:* ]]; then
    echo "Isolated package already exists; refusing to overwrite it: $candidate"
    exit 1
  fi
done
cleanup() {
  adb shell am force-stop "$package" >/dev/null 2>&1 || true
  adb uninstall "$package.test" >/dev/null 2>&1 || true
  adb uninstall "$package" >/dev/null 2>&1 || true
}
trap cleanup EXIT
adb install "$app"
adb install "$test_app"
adb shell getprop ro.build.version.sdk > "$report/api-level.txt"
adb shell wm size > "$report/display.txt"
adb shell wm density >> "$report/display.txt"
adb shell am instrument -w -r -e class dev.unified.app.ConnectionDeviceTest,dev.unified.app.HttpsRecoveryDeviceTest \
  "$package.test/androidx.test.runner.AndroidJUnitRunner" | tee "$report/instrumentation.txt"
grep -Eq 'OK \([0-9]+ tests?\)' "$report/instrumentation.txt"
# Exercise the installed crash handler through Android, then start a fresh process to export.
adb shell am start -W -n "$package/dev.unified.app.MainActivity" > "$report/start.txt"
adb shell am crash "$package" > "$report/crash-request.txt"
for attempt in {1..20}; do
  pid=$(adb shell pidof "$package" || true)
  [[ -z "$pid" ]] && break
  sleep 1
done
[[ -z "$pid" ]] || { echo "Isolated process did not exit after the crash request."; exit 1; }
adb shell am instrument -w -r -e class dev.unified.app.DiagnosticsDeviceTest \
  "$package.test/androidx.test.runner.AndroidJUnitRunner" | tee "$report/crash-restart.txt"
# Restrict diagnostics to this isolated app; never dump other apps' logs.
uid=$(adb shell pm list packages -U "$package" | awk -v name="package:$package" '$1 == name {sub(/^uid:/, "", $2); print $2}' | tr -d '\r')
if [[ "$uid" =~ ^[0-9]+$ ]]; then
  adb logcat -d --uid="$uid" -t 500 -v brief > "$report/app-log.txt"
fi
grep -Eq 'OK \([0-9]+ tests?\)' "$report/crash-restart.txt"
