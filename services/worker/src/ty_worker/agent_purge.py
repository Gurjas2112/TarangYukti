"""Nightly purge of conversation memory (spec §6.4.5): threads unused for 30 days are deleted with LangGraph's
own `delete_thread` (all checkpoints and writes), then their agent.threads rows.

    uv run python -m ty_worker.agent_purge [--days 30] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging

import psycopg
from psycopg.rows import dict_row
from ty_common.settings import get_settings

log = logging.getLogger(__name__)
RETENTION_DAYS = 30


def purge(days: int = RETENTION_DAYS, dry_run: bool = False) -> list[str]:
    from langgraph.checkpoint.postgres import PostgresSaver

    s = get_settings()
    if s.worker_database_url is None:
        raise RuntimeError("WORKER_DATABASE_URL is not set")
    with psycopg.connect(
        s.worker_database_url.get_secret_value(),
        autocommit=True,
        row_factory=dict_row,
        options="-c search_path=agent",
    ) as conn:
        rows = conn.execute(
            "select thread_id from agent.threads where last_seen < now() - make_interval(days => %s)", (days,)
        ).fetchall()
        ids = [str(r["thread_id"]) for r in rows]
        if dry_run or not ids:
            return ids
        saver = PostgresSaver(conn)
        for tid in ids:
            saver.delete_thread(tid)
            conn.execute("delete from agent.threads where thread_id = %s", (tid,))
    return ids


async def run() -> None:
    ids = await asyncio.to_thread(purge)
    log.info("agent_purge: deleted %d threads idle for %d days", len(ids), RETENTION_DAYS)


def main() -> None:
    ap = argparse.ArgumentParser(prog="ty_worker.agent_purge")
    ap.add_argument("--days", type=int, default=RETENTION_DAYS)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ids = purge(a.days, a.dry_run)
    print(f"{'would delete' if a.dry_run else 'deleted'} {len(ids)} threads")


if __name__ == "__main__":
    main()
