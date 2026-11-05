#!/usr/bin/env bash
# video/scripts/render_all.sh <walkthrough-root> [lang …]   (no langs = every released language) — spec §17.15.
# Per language: assets → full video (1920×1080) → portrait cut (1080×1920) → chapters.txt → one MP4 per chapter.
# DRAFT=1 allows screens missing from the capture (labelled cards) for a draft render.
set -euo pipefail
ROOT=$(cd "$1" && pwd)
shift
cd "$(dirname "$0")/.."
LANGS=${*:-$(python ../scripts/capture_tools.py released)}
[ -n "$LANGS" ] || { echo "no released language yet; name the languages to render" >&2; exit 2; }
for L in $LANGS; do
  (cd ../services/channels && PYTHONIOENCODING=utf-8 uv run python ../../video/scripts/build_assets.py "$ROOT" "$L" \
    ${DRAFT:+--allow-missing})
  mkdir -p "out/$L/chapters"
  for layout in landscape portrait; do printf '{"lang":"%s","layout":"%s"}' "$L" "$layout" >"props.$L.$layout.json"; done
  npx remotion render src/index.ts KadalMitraStory "out/$L/kadal-mitra-story-$L.mp4" --props="props.$L.landscape.json"
  npx remotion render src/index.ts KadalMitraStoryVertical "out/$L/kadal-mitra-story-$L-vertical.mp4" \
    --props="props.$L.portrait.json"
  node scripts/chapters.mjs "public/timeline.$L.json" >"out/$L/chapters.txt"
  node scripts/chapters.mjs "public/timeline.$L.json" --ranges | while read -r n start end; do
    npx remotion render src/index.ts KadalMitraStory "out/$L/chapters/$(printf %02d "$n").mp4" \
      --props="props.$L.landscape.json" --frames="$start-$end"
  done
done
