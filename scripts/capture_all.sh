#!/usr/bin/env bash
# scripts/capture_all.sh <capture-apk> <live-apk> [lang …]   (no langs = every released language)
# Spec §17.14.4: Android flows, web flows and the release smoke per language, then the coverage check.
set -euo pipefail
cd "$(dirname "$0")/.."
CAP=${1:?usage: capture_all.sh <capture-apk> <live-apk> [lang …]}
LIVE=${2:?live apk}
shift 2
LANGS=${*:-$(python scripts/capture_tools.py released)}
[ -n "$LANGS" ] || { echo "no released language yet; name the languages to capture" >&2; exit 2; }
VERSION=$(python -c "import json; print(json.load(open('apps/app/package.json'))['version'])")
ROOT="artifacts/app-walkthrough/${VERSION}-$(date +%F)"
mkdir -p "$ROOT/apk"
if [ -f "$LIVE.sha256" ]; then (cd "$(dirname "$LIVE")" && sha256sum -c "$(basename "$LIVE").sha256"); fi
cp "$LIVE" "$ROOT/apk/kadal-mitra-${VERSION}.apk"
cp "$CAP" "$ROOT/apk/kadal-mitra-${VERSION}-capture.apk"
(cd "$ROOT/apk" && sha256sum ./*.apk >SHA256SUMS)
STATUS=0
for L in $LANGS; do
  echo "== $L"
  scripts/capture_walkthrough.sh "$CAP" "$L" "$ROOT" || STATUS=1 # Android A01–A21
  WALK_OUT="$PWD/$ROOT/$L/web" APP_LANG="$L" pnpm -C apps/app exec playwright test e2e/web/walkthrough.spec.ts \
    --project=desktop || STATUS=1 # web W01–W08
done
scripts/release_smoke.sh "$LIVE" "$ROOT/release-smoke" || STATUS=1 # R01 on Tier 1
# shellcheck disable=SC2086
python scripts/check_coverage.py "$ROOT" --langs $LANGS || STATUS=1 # README + coverage-report.json
echo "$ROOT"
exit $STATUS
