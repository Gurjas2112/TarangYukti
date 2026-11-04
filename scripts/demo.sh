#!/usr/bin/env bash
# Demo day on the laptop (spec §15.1, §16.1): every service in snapshot mode. Buttons, map, alerts and document
# search work without the data-source APIs; free-form chat and voice still need the network.
#   SNAPSHOT_DATE=2026-11-02 scripts/demo.sh      # then open http://localhost:8081 (web) or the Android dev build
set -euo pipefail
cd "$(dirname "$0")/.."
export DATA_MODE=snapshot
: "${SNAPSHOT_DATE:?set SNAPSHOT_DATE to a captured snapshot (make snapshot DATE=YYYY-MM-DD)}"
export SNAPSHOT_DATE
LOGS="$PWD/artifacts/demo-logs"
mkdir -p "$LOGS"

make snapshot-download DATE="$SNAPSHOT_DATE"

(cd services/mcp && nohup uv run python -m tarangyukti.server > "$LOGS/mcp.log" 2>&1 &)
(cd services/channels && nohup uv run python -m ty_channels.serve --port 8002 > "$LOGS/channels.log" 2>&1 &)
(cd apps/agent && nohup uv run python serve.py --port 8123 > "$LOGS/agent.log" 2>&1 &)
(cd services/worker && nohup uv run python -m ty_worker > "$LOGS/worker.log" 2>&1 &)
(cd services/copilot && nohup node --env-file-if-exists=.env src/server.ts > "$LOGS/copilot.log" 2>&1 &)
(cd apps/app && npx expo export -p web > "$LOGS/web-export.log" 2>&1 && nohup node e2e/web/serve.mjs > "$LOGS/web.log" 2>&1 &)

for _ in $(seq 1 90); do
  if curl -s http://127.0.0.1:8002/health > /dev/null && curl -s http://127.0.0.1:8123/ok > /dev/null; then break; fi
  sleep 2
done
WEB=http://127.0.0.1:8081 scripts/smoke.sh
echo "demo ready: web http://localhost:8081 · Expert http://localhost:8081/expert · logs in artifacts/demo-logs/"
