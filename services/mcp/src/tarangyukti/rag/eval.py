"""Retrieval evaluation on the golden set (spec §6.2.9, §14.3): `make eval-rag`.

    uv run python -m tarangyukti.rag.eval [--golden apps/agent/tests/golden.jsonl] [--report docs/eval-report.md]

Each golden row: {"id", "lang", "question", "expected": [source_id prefixes]}; an empty `expected` marks a
question the corpus cannot answer (it must come back `relevant: false`).

Measures recall@8 (an expected document among the 8 cited passages) per language, the "nothing relevant"
accuracy on unanswerable questions, and the best-similarity distributions used to calibrate RAG_MIN_SIM.
Ragas faithfulness / answer relevancy need generated answers and run with the agent (Milestone 5).
Gate (prompt §8): recall@8 ≥ 0.9.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ty_common.cache import Cache, set_cache
from ty_common.settings import find_config_dir, get_settings

from . import search

GATE_RECALL = 0.9


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def hit(expected: list[str], sources: list[str]) -> bool:
    return any(s.startswith(e) for e in expected for s in sources)


def best_threshold(pos: list[float], neg: list[float]) -> float | None:
    """Threshold maximising balanced accuracy between answerable (pos) and unanswerable (neg) best sims."""
    if not pos or not neg:
        return None
    cands = sorted(set(pos + neg))
    best = max((sum(p >= t for p in pos) / len(pos) + sum(n < t for n in neg) / len(neg)) / 2 for t in cands)
    good = [t for t in cands if (sum(p >= t for p in pos) / len(pos) + sum(n < t for n in neg) / len(neg)) / 2 == best]
    # middle of the best band, so a small drift in either direction keeps the same decisions
    lo = max([n for n in neg if n < min(good)], default=min(good))
    return round((lo + min(good)) / 2, 3)


async def run(golden: Path) -> dict[str, Any]:
    set_cache(Cache(disabled=True))  # measure the real pipeline, not the cache
    rows = load(golden)
    per_lang: dict[str, list[bool]] = defaultdict(list)
    unans: dict[str, list[bool]] = defaultdict(list)
    pos: list[float] = []
    neg: list[float] = []
    misses = []
    for r in rows:
        res = await search.kb_search(r["question"], lang=r["lang"])
        d = res["data"]
        if d.get("available") is False:
            raise SystemExit(f"knowledge base unavailable: {d['reason']}")
        sources = [c["document"]["source_id"] for c in d["chunks"]]
        best = d["best_sim"]
        if r["expected"]:
            ok = hit(r["expected"], sources)
            per_lang[r["lang"]].append(ok)
            if best is not None and ok:  # calibrate only on questions the corpus really answered
                pos.append(best)
            if not ok:
                misses.append(
                    {
                        "id": r["id"],
                        "question": r["question"],
                        "expected": r["expected"],
                        "got": sources[:3],
                        "best_sim": best,
                    }
                )
        else:
            unans[r["lang"]].append(not d["relevant"])
            if best is not None:
                neg.append(best)
    recall = {k: round(sum(v) / len(v), 3) for k, v in per_lang.items()}
    overall = round(sum(sum(v) for v in per_lang.values()) / max(1, sum(len(v) for v in per_lang.values())), 3)
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "questions": len(rows),
        "recall_at_8": recall,
        "recall_at_8_overall": overall,
        "gate_recall": GATE_RECALL,
        "gate_passed": overall >= GATE_RECALL,
        "unanswerable_detected": {k: round(sum(v) / len(v), 3) for k, v in unans.items()},
        "best_sim_answerable": _dist(pos),
        "best_sim_unanswerable": _dist(neg),
        "rag_min_sim_current": get_settings().rag_min_sim,
        "rag_min_sim_suggested": best_threshold(pos, neg),
        "misses": misses,
    }


def _dist(xs: list[float]) -> dict[str, float] | None:
    if not xs:
        return None
    return {"min": round(min(xs), 3), "median": round(statistics.median(xs), 3), "max": round(max(xs), 3)}


def to_markdown(r: dict[str, Any]) -> str:
    lines = [
        f"## RAG retrieval evaluation — {r['at']}",
        "",
        f"Golden set: {r['questions']} questions. Gate: recall@8 ≥ {r['gate_recall']} — "
        f"**{'passed' if r['gate_passed'] else 'NOT passed'}** (overall {r['recall_at_8_overall']}).",
        "",
        "| Measure | Value |",
        "|---|---|",
        *[f"| recall@8 ({k}) | {v} |" for k, v in sorted(r["recall_at_8"].items())],
        *[f"| unanswerable recognised ({k}) | {v} |" for k, v in sorted(r["unanswerable_detected"].items())],
        f"| best similarity, answerable | {r['best_sim_answerable']} |",
        f"| best similarity, unanswerable | {r['best_sim_unanswerable']} |",
        f"| RAG_MIN_SIM current / suggested | {r['rag_min_sim_current']} / {r['rag_min_sim_suggested']} |",
        "",
        "Ragas faithfulness and answer relevancy need generated answers; they run with the agent (Milestone 5).",
    ]
    if r["misses"]:
        lines += ["", "Misses:", ""] + [
            f"- `{m['id']}` {m['question']} — expected {m['expected']}, got {m['got']}" for m in r["misses"]
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    repo = find_config_dir().parent
    ap = argparse.ArgumentParser(prog="tarangyukti.rag.eval")
    ap.add_argument("--golden", type=Path, default=repo / "apps" / "agent" / "tests" / "golden.jsonl")
    ap.add_argument("--report", type=Path, default=None, help="append the result to this markdown file")
    a = ap.parse_args()
    result = asyncio.run(run(a.golden))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if a.report:
        with a.report.open("a", encoding="utf-8") as f:
            f.write("\n" + to_markdown(result))
    raise SystemExit(0 if result["gate_passed"] else 1)


if __name__ == "__main__":
    main()
