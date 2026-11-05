#!/usr/bin/env bash
# scripts/scenario.sh <flow|scenario> — put the laptop backend and the emulator into the state a flow needs
# (spec §17.14.3). Flow names are looked up in apps/app/e2e/maestro/scenarios.yaml; anything else is "normal".
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/capture_env.sh
ARG=${1:?usage: scenario.sh <flow|scenario>}
NAME=$(python scripts/capture_tools.py scenario "$ARG")
BACKEND=$NAME
[ "$NAME" = font-scale-200 ] && BACKEND=normal
curl -fsS -X POST "$CHANNELS_LOCAL/admin/capture/scenario" -H "X-Capture-Token: ${CAPTURE_TOKEN:?CAPTURE_TOKEN not set}" \
  -H 'content-type: application/json' -d "{\"name\":\"$BACKEND\"}" >/dev/null
if [ "$NAME" = font-scale-200 ]; then
  "$ADB" shell settings put system font_scale 2.0
else
  "$ADB" shell settings put system font_scale 1.0
fi
if [ "$NAME" = brief-now ] && [ -n "${CAPTURE_FISHER_ID:-}" ]; then # the test fisher's brief, sent now
  (cd services/worker && uv run python -m ty_worker.morning --user "$CAPTURE_FISHER_ID" >/dev/null) || true
fi
echo "$NAME"
