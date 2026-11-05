"""Agent improvement evaluation (spec §10.4): golden questions through the running agent, scored per language,
recorded in TraceRoot with `evaluate()` (one `candidate_version` per git commit) when tracing is on.

    cd apps/agent && uv run python ../../scripts/eval_traceroot.py [--per-lang 5] [--langs ml-IN ur-IN]
                                                                     [--cross] [--out docs/improvement/runs]

Needs the agent (and mcp) running locally — with TRACEROOT_ENABLED=true so the agent's own traces carry the
LLM and tool spans the detectors judge. Test traffic only: refuses to run with ENV=live (SEC-14).

Scorers (deterministic; the LLM-judge detectors live in TraceRoot, docs/improvement/detectors.md):
  same_language     reply body in the language's script (the validator's own check)
  footer            ends with that language's approved "advisory only" footer
  no_unsafe_word    never "safe" without "advisory"
  draft_clean       the validator removed nothing (no ungrounded number, dropped quote or language mismatch)
  no_template       answered by the agent, not by the fallback template
  no_figures_if_unanswerable  unanswerable golden questions get no figures (refusal wording: detector D5)
Writes <out>/<sha>-<date>.json with per-language rates for docs/improvement/report.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "agent"))  # the agent's validator and templates

from ty_common.settings import get_settings  # noqa: E402

from src import templates  # noqa: E402
from src.validator import language_ok  # noqa: E402

GOLDEN = ROOT / "apps" / "agent" / "tests"
AGENT = os.environ.get("AGENT_URL", "http://127.0.0.1:8123")


def rows(per_lang: int, langs: list[str] | None, cross: bool) -> list[dict[str, Any]]:
    files = [*sorted((GOLDEN / "golden").glob("*-IN.jsonl")), GOLDEN / "golden.jsonl"]
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                by_lang[r["lang"]].append(r)
    out = []
    for lang, rs in sorted(by_lang.items()):
        if langs and lang not in langs:
            continue
        answerable = [r for r in rs if r["expected"]][: max(1, per_lang - 1)]
        unanswerable = [r for r in rs if not r["expected"]][:1]
        out += answerable + unanswerable
    if cross:
        for line in (GOLDEN / "golden" / "cross.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line) | {"set": "cross"})
    return out


def ask(question: str, lang: str) -> dict[str, Any]:
    """One question through POST /agent, the way ty-copilot sends it. Returns the reply and the final state."""
    body = {
        "threadId": f"eval-{uuid.uuid4()}",
        "runId": str(uuid.uuid4()),
        "state": {},
        "messages": [{"id": str(uuid.uuid4()), "role": "user", "content": question}],
        "tools": [],
        "context": [],
        "forwardedProps": {"lang": lang, "mode": "simple"},
    }
    reply, state = "", {}
    with httpx.stream("POST", f"{AGENT}/agent", json=body, timeout=180) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:])
            except ValueError:
                continue
            if ev.get("type") == "MESSAGES_SNAPSHOT":
                for m in reversed(ev.get("messages", [])):
                    if m.get("role") == "assistant" and isinstance(m.get("content"), str):
                        reply = m["content"]
                        break
            elif ev.get("type") == "STATE_SNAPSHOT":
                state = ev.get("snapshot") or state
    return {"reply": reply, "guard": state.get("guard") or {}, "fallback": state.get("fallback")}


def scores(row: dict[str, Any], out: dict[str, Any]) -> dict[str, bool]:
    lang, reply, guard = row["lang"], out["reply"], out["guard"]
    foot = templates.footer(lang)
    body = reply[: -len(foot)].strip() if reply.endswith(foot) else reply
    s = {
        "same_language": bool(body) and language_ok(body, lang),
        "footer": reply.strip().endswith(foot),
        "no_unsafe_word": not ("safe" in reply.lower() and "advisory" not in reply.lower()),
        "draft_clean": not any(guard.get(k) for k in ("ungrounded_number", "quote_dropped", "language_mismatch")),
        "no_template": not out.get("fallback"),
    }
    if not row["expected"]:
        # An unanswerable question (a market price, a cricket score) must get no figures at all; whether the refusal
        # names the right official source is judged by TraceRoot detector D5 in any language.
        s["no_figures_if_unanswerable"] = not re.search(r"\d", body)
    return s


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-lang", type=int, default=5)
    ap.add_argument("--langs", nargs="*")
    ap.add_argument("--cross", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "improvement" / "runs")
    ap.add_argument("--concurrency", type=int, default=3)
    a = ap.parse_args()
    s = get_settings()
    if s.env == "live":
        raise SystemExit("test traffic only (SEC-14): never run against live")
    data = rows(a.per_lang, a.langs, a.cross)
    sha = git_sha()
    results: dict[str, dict[str, Any]] = {}

    def task(inp: dict[str, Any]) -> dict[str, Any]:
        out = ask(inp["question"], inp["lang"])
        results[inp["id"]] = {"row": inp, "out": out, "scores": scores(inp, out)}
        return out

    def scorer(name: str) -> Any:
        def fn(ctx: Any) -> bool | None:
            return results.get(ctx.input["id"], {}).get("scores", {}).get(name)

        fn.__name__ = name
        return fn

    names = ["same_language", "footer", "no_unsafe_word", "draft_clean", "no_template", "no_figures_if_unanswerable"]
    cases = [{"input": r, "expected": r["expected"], "metadata": {"lang": r["lang"], "id": r["id"]}} for r in data]
    traced = s.traceroot_enabled and s.traceroot_api_key is not None
    try:
        import traceroot

        dataset: Any = cases
        if traced:
            from traceroot.eval import Dataset, PlatformDatasetSync

            key = s.traceroot_api_key.get_secret_value()  # type: ignore[union-attr]
            traceroot.initialize(api_key=key, host_url=s.traceroot_host_url)
            # The golden questions as a TraceRoot dataset; a changed set publishes a new version (never interactive).
            dataset = Dataset("tarangyukti-golden", "Golden questions, every language (spec §10.4)")
            for c in cases:
                dataset.add(c["input"], expected=c["expected"], metadata=c["metadata"], id=c["input"]["id"])
            dataset.push(PlatformDatasetSync(api_key=key, host_url=s.traceroot_host_url), on_existing=lambda _: True)
        traceroot.evaluate(
            name="tarangyukti-golden",
            dataset=dataset,
            task=task,
            scorers=[scorer(n) for n in names],
            candidate_version=sha,
            local=not traced,
            max_concurrency=a.concurrency,
            environment=s.traceroot_environment,
            metadata={"model": s.orca_model},
            progress=False,
        )
        if traced:
            traceroot.flush()
    except ImportError:  # TraceRoot SDK missing: same scores, recorded locally only
        for c in cases:
            task(c["input"])

    per_lang: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for r in results.values():
        key = "cross" if r["row"].get("set") == "cross" else r["row"]["lang"]
        for n, v in r["scores"].items():
            per_lang[key][n].append(bool(v))
    summary = {
        k: {n: round(sum(v) / len(v), 3) for n, v in sc.items()} | {"runs": len(next(iter(sc.values())))}
        for k, sc in sorted(per_lang.items())
    }
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / f"{sha}-{datetime.now(UTC):%Y%m%d-%H%M}.json"
    path.write_text(
        json.dumps(
            {
                "candidate_version": sha,
                "traced_to_traceroot": traced,
                "model": s.orca_model,
                "runs": len(results),
                "summary": summary,
                "failures": [
                    {"id": i, "lang": r["row"]["lang"], "failed": [n for n, v in r["scores"].items() if not v],
                     "reply": r["out"]["reply"][:300]}
                    for i, r in sorted(results.items())
                    if not all(r["scores"].values())
                ],
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=1))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
