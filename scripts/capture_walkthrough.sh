#!/usr/bin/env bash
# scripts/capture_walkthrough.sh <capture-apk> <lang> <out-root> — one language (spec §17.14.4), Windows Git Bash.
# Emulator + Maestro + scrcpy: every Android flow in its scenario, one screenshot per step, one full recording.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/capture_env.sh
APK=${1:?usage: capture_walkthrough.sh <capture-apk> <lang> <out-root>}
LANG_CODE=${2:?lang}
ROOT=${3:?out-root}
OUT="$ROOT/$LANG_CODE"
TMP="${TEMP:-/tmp}/ty-capture-$LANG_CODE"
rm -rf "$TMP" && mkdir -p "$TMP/maestro" "$OUT/android" "$OUT/video"

# 1 · emulator up and booted
if ! "$ADB" devices | grep -q '^emulator-'; then
  "$EMULATOR" -avd "$AVD" -no-boot-anim -no-snapshot-save >/dev/null 2>&1 &
  "$ADB" wait-for-device
  until [ "$("$ADB" shell getprop sys.boot_completed | tr -d '\r')" = "1" ]; do sleep 3; done
fi
SERIAL=$("$ADB" devices | awk '/^emulator-/{print $1; exit}')

# 2 · clean, repeatable status bar (demo mode) and a fresh install
"$ADB" shell settings put global sysui_demo_allowed 1
for c in "clock -e hhmm 0430" "battery -e level 100 -e plugged false" \
  "network -e mobile show -e level 4 -e datatype 4g" "notifications -e visible false"; do
  # shellcheck disable=SC2086
  "$ADB" shell am broadcast -a com.android.systemui.demo -e command $c >/dev/null
done
"$ADB" uninstall "$PKG" >/dev/null 2>&1 || true
"$ADB" install -r "$APK" >/dev/null

# 3 · the full-length recording (scrcpy has no 3-minute limit)
scrcpy -s "$SERIAL" --no-playback --no-window --record="$TMP/walkthrough.mkv" >"$TMP/scrcpy.log" 2>&1 &
REC=$!
T0=$(date +%s%3N)
sleep 3

# 4 · every Android flow in order, each in its scenario, logging where it sits in the recording
set +e
FAILED=()
for f in 00-launch $(cd apps/app/e2e/maestro/flows && ls A[0-9][0-9]-*.yaml | sed 's/\.yaml$//' | sort); do
  scripts/scenario.sh "$f" >/dev/null || FAILED+=("$f:scenario")
  S0=$(($(date +%s%3N) - T0))
  if [ "$f" = 00-launch ]; then FLOW=apps/app/e2e/maestro/00-launch.yaml; else FLOW=apps/app/e2e/maestro/flows/$f.yaml; fi
  if "$MAESTRO" test --device "$SERIAL" -e APP_LANG="$LANG_CODE" --test-output-dir "$TMP/maestro/$f" "$FLOW" \
    >"$TMP/maestro/$f.log" 2>&1; then
    echo "  $LANG_CODE $f: ok"
  else
    FAILED+=("$f")
    echo "  $LANG_CODE $f: FAILED (log: $OUT/maestro/$f.log)"
  fi
  python scripts/capture_tools.py segment "$TMP/segments.json" "$f" "$S0" "$(($(date +%s%3N) - T0))"
done
scripts/scenario.sh normal >/dev/null
set -e

# 5 · stop the recording and remux to MP4 without re-encoding
sleep 2
kill -INT "$REC" 2>/dev/null || true
wait "$REC" 2>/dev/null || true
ffmpeg -loglevel error -y -i "$TMP/walkthrough.mkv" -c copy "$OUT/video/full-walkthrough.mp4" || true
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/video/full-walkthrough.mp4" 2>/dev/null || echo 0)

# 6 · screenshots by flow/step, raw Maestro output, segments and the manifest
N=$(python scripts/capture_tools.py collect "$TMP/maestro" . --to "$OUT/android")
cp -r "$TMP/maestro" "$OUT/maestro"
cp "$TMP/segments.json" "$OUT/video/segments.json"
python scripts/capture_tools.py manifest "$OUT/manifest.json" "$LANG_CODE" "$AVD" "$DUR" "${FAILED[@]}"
"$ADB" shell am broadcast -a com.android.systemui.demo -e command exit >/dev/null
echo "$LANG_CODE: $N screenshots, ${DUR%.*} s of video, ${#FAILED[@]} flows failed"
[ ${#FAILED[@]} -eq 0 ]
