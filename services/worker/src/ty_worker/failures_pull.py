"""make failures-pull: Guardrail review's "Add to failures dataset" → new rows in tests/failures/failures.yaml.

Each candidate becomes a `layer: triage` row (id locked in ids.lock, never removed) with the question, language,
mode and versions of the answer. Triage rows are not replayed yet: the fix moves a row to `agent` or `tools` with
the expected behaviour, and the fix is done only when that row passes (prompt §13). Commit the change in a PR.

    uv run python -m ty_worker.failures_pull [--dry-run]
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import yaml
from psycopg.rows import dict_row
from ty_common.settings import find_config_dir, get_settings

PENDING = """
select f.id, f.wrong, f.expect, f.created_at, a.question, a.lang, a.mode, a.reply, a.model, a.prompt_version,
       a.config_version, a.guard
from failure_candidates f left join answers a on a.id = f.answer_id
where f.pulled_at is null order by f.id
"""


def failures_dir() -> Path:
    return find_config_dir().parent / "tests" / "failures"


def next_ids(existing: list[str], n: int) -> list[str]:
    top = max((int(x.split("-")[1]) for x in existing if x.startswith("F-")), default=0)
    return [f"F-{top + i:03d}" for i in range(1, n + 1)]


def row(fid: str, c: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fid,
        "found": f"{c['created_at']:%Y-%m-%d} · admin Guardrail review",
        "layer": "triage",
        "input": {"text": c["question"], "lang": c["lang"], "mode": c["mode"]},
        "snapshot": None,
        "wrong": c["wrong"],
        "cause": "TODO(tarangyukti): find the cause",
        "guard": "TODO(tarangyukti): the guard that stops it",
        "expect": {"note": c["expect"]} if c["expect"] else {},
        "seen_with": {"model": c["model"], "prompt": c["prompt_version"], "config": c["config_version"]},
    }


def main() -> None:
    ap = argparse.ArgumentParser(prog="ty_worker.failures_pull")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    url = get_settings().worker_database_url
    if url is None:
        raise SystemExit("WORKER_DATABASE_URL is not set")
    d = failures_dir()
    data = yaml.safe_load((d / "failures.yaml").read_text(encoding="utf-8")) or []
    with psycopg.connect(url.get_secret_value(), row_factory=dict_row) as conn:
        pending = conn.execute(PENDING).fetchall()
        if not pending:
            print("no new candidates")
            return
        ids = next_ids([r["id"] for r in data], len(pending))
        rows = [row(fid, c) for fid, c in zip(ids, pending, strict=True)]
        text = yaml.safe_dump(rows, allow_unicode=True, sort_keys=False, width=110)
        if a.dry_run:
            print(text)
            return
        with (d / "failures.yaml").open("a", encoding="utf-8") as f:
            f.write("\n" + text)
        with (d / "ids.lock").open("a", encoding="utf-8") as f:
            f.write("".join(f"{fid}\n" for fid in ids))
        conn.execute(
            "update failure_candidates set pulled_at = %s where id = any(%s)",
            (datetime.now(UTC), [c["id"] for c in pending]),
        )
    print(f"added {', '.join(ids)} — fill in cause/guard/expect, move to layer agent/tools with the fix, open a PR")


if __name__ == "__main__":
    main()
