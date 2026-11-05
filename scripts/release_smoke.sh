#!/usr/bin/env bash
# scripts/release_smoke.sh <live-apk> <out> [lang] — R01: the live APK against Tier 1 (spec §17.14.4).
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/capture_env.sh
APK=${1:?usage: release_smoke.sh <live-apk> <out> [lang]}
OUT=${2:?out}
LANG_CODE=${3:-en-IN}
SERIAL=$("$ADB" devices | awk '/^emulator-/{print $1; exit}')
"$ADB" uninstall "$PKG" >/dev/null 2>&1 || true
"$ADB" install -r "$APK" >/dev/null
TMP="${TEMP:-/tmp}/ty-r01"
rm -rf "$TMP" && mkdir -p "$OUT"
"$MAESTRO" test --device "$SERIAL" -e APP_LANG="$LANG_CODE" --test-output-dir "$TMP" \
  apps/app/e2e/maestro/flows/R01-release-smoke.yaml >"$OUT/r01.log" 2>&1
N=$(python scripts/capture_tools.py collect "$TMP" . --to "$OUT")
echo "release smoke: ok ($N screenshots)"
