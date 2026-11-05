"""Draft the per-language golden sets (spec §6.5, Milestone 10a): 20 questions per language, machine-translated
from the English set with sarvam-translate:v1 and marked `"draft": true` until the language's reviewers check them.

    cd services/channels && uv run python ../../scripts/golden_draft.py [--only ml-IN gu-IN]

Writes apps/agent/tests/golden/<code>.jsonl. English and Tamil keep their hand-checked rows in golden.jsonl.
A question whose translation changed a number (for example the year 2024) is skipped, never stored wrong.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from i18n_draft import ROOT, Translator, sync_languages  # noqa: E402

GOLDEN = ROOT / "apps" / "agent" / "tests" / "golden.jsonl"
OUT = ROOT / "apps" / "agent" / "tests" / "golden"
BASE = [  # 16 answerable across every document type + 4 the corpus cannot answer
    "mz-territorial", "mz-eez", "mz-foreign-fishing", "tn-purpose", "tn-mechanised", "tn-prohibit-area",
    "tn-registration", "cm-total-2024", "cm-top-state", "cm-top-species", "sop-cyclone-at-sea", "sop-high-wave",
    "sop-cross-border", "sop-drift-border", "sop-coast-guard", "ban-east-coast",
    "x-fish-price", "x-cricket", "x-recipe", "x-loan",
]  # fmt: skip
SKIP = {"en-IN", "ta-IN"}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    rows = {json.loads(x)["id"]: json.loads(x) for x in GOLDEN.read_text(encoding="utf-8").splitlines() if x.strip()}
    base = [rows[f"en-{b}"] for b in BASE]
    tr = Translator()
    OUT.mkdir(exist_ok=True)
    for lang in sync_languages():
        code = lang["code"]
        if code in SKIP or (a.only and code not in a.only):
            continue
        out = await asyncio.gather(*(tr.one(r["question"], lang["sarvam_code"]) for r in base))
        lines = []
        for r, q in zip(base, out, strict=True):
            if q is None:
                continue
            lines.append(
                json.dumps(
                    {"id": f"{code}-{r['id'][3:]}", "lang": code, "question": q, "expected": r["expected"], "draft": True},
                    ensure_ascii=False,
                )
            )
        (OUT / f"{code}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{code}: {len(lines)} questions")


if __name__ == "__main__":
    asyncio.run(main())
