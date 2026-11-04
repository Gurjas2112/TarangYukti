#!/usr/bin/env bash
# Smoke test (spec §15.3): every public path a fisher and the Expert console touch, laptop or Azure.
#   scripts/smoke.sh                                  # laptop: channels :8002, copilot :8200, agent :8123
#   CHANNELS=https://… COPILOT=https://… WEB=https://… scripts/smoke.sh     # Azure (agent and MCP are internal there)
set -u
CHANNELS=${CHANNELS:-http://127.0.0.1:8002}
COPILOT=${COPILOT:-http://127.0.0.1:8200}
AGENT=${AGENT:-http://127.0.0.1:8123}
WEB=${WEB:-}
fail=0

check() { # name, url, expected substring
  local out code body
  out=$(curl -s -m 120 -w '\n%{http_code}' "$2")
  code=$(printf '%s' "$out" | tail -n 1)
  body=$(printf '%s' "$out" | sed '$d')
  if [ "$code" = "200" ] && printf '%s' "$body" | grep -qF -- "$3"; then
    printf '  ok    %-26s %s\n' "$1" "$code"
  else
    printf '  FAIL  %-26s %s %s\n' "$1" "$code" "$(printf '%s' "$body" | head -c 120)"
    fail=1
  fi
}

echo "smoke: $CHANNELS"
check "channels /health" "$CHANNELS/health" "ok"
check "languages (23)" "$CHANNELS/languages" "ta-IN"
check "harbours" "$CHANNELS/harbours" "rameswaram"
check "today's sea card" "$CHANNELS/brief?harbour=rameswaram&boat_type=small_frp&lang=en-IN" "Advisory only"
check "expert plan + ledger" "$CHANNELS/expert/plan?harbour=rameswaram&boat_type=small_frp" '"H8"'
check "border line layer" "$CHANNELS/layers/imbl" "Feature"
check "help (grievance)" "$CHANNELS/help" "grievance_officer"
check "app version" "$CHANNELS/app/version" "minVersionCode"
check "copilot /health" "$COPILOT/health" "ok"
case "$CHANNELS" in http://127.0.0.1*) check "agent /ok" "$AGENT/ok" "true" ;; esac
if [ -n "$WEB" ]; then check "web build" "$WEB/" 'id="root"'; fi

if [ "$fail" = 0 ]; then echo "smoke: all green"; else echo "smoke: FAILED"; exit 1; fi
