"""Sends queued pushes: every `alerts` row with status 'pending' goes to every push subscription of its user,
after the alert budget and quiet hours (budget.py). Three failed attempts mark it 'failed' (admin console red).

Runs every minute in the worker, and right after the brief job or a test push queues a row.

    uv run python -m ty_worker.outbox
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time
from typing import Any

import psycopg
from psycopg.rows import dict_row
from ty_common.settings import get_settings

from . import budget, push
from .runtime import run_async

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


async def connect() -> psycopg.AsyncConnection[dict[str, Any]]:
    url = get_settings().worker_database_url
    if url is None:
        raise RuntimeError("WORKER_DATABASE_URL is not set")
    return await psycopg.AsyncConnection.connect(
        url.get_secret_value(), autocommit=True, row_factory=dict_row, prepare_threshold=None
    )


def message(row: dict[str, Any]) -> push.Message:
    url = row.get("url") or ("/" if row["kind"] in ("brief", "test") else "/alerts")
    return {"id": str(row["id"]), "kind": row["kind"], "title": row["title"], "body": row["body"], "url": url}


async def _decision(conn: psycopg.AsyncConnection[dict[str, Any]], a: dict[str, Any], now: datetime) -> str:
    if a["kind"] != "alert":
        return budget.decide(kind=a["kind"], critical=a["critical"], now=now)
    prefs = await (
        await conn.execute("select quiet_from, quiet_to from user_prefs where user_id = %s", (a["user_id"],))
    ).fetchone()
    sent = await (
        await conn.execute(
            """select count(*) as n from alerts where user_id = %s and kind = 'alert' and not critical
               and status = 'sent' and sent_at >= %s""",
            (a["user_id"], budget.ist_day_start(now)),
        )
    ).fetchone()
    last = await (
        await conn.execute(
            """select max(sent_at) as at from alerts where user_id = %s and boat_id is not distinct from %s
               and rule = %s and status = 'sent'""",
            (a["user_id"], a["boat_id"], a["rule"]),
        )
    ).fetchone()
    return budget.decide(
        kind="alert",
        critical=a["critical"],
        now=now,
        quiet_from=(prefs or {}).get("quiet_from") or time(21, 0),
        quiet_to=(prefs or {}).get("quiet_to") or time(3, 30),
        sent_non_critical_today=int((sent or {}).get("n") or 0),
        last_same_rule_at=(last or {}).get("at"),
    )


async def send_pending(conn: psycopg.AsyncConnection[dict[str, Any]], only: str | None = None) -> dict[str, int]:
    now = datetime.now(UTC)
    rows = await (
        await conn.execute(
            """select * from alerts where status = 'pending' and attempts < %s
               and created_at > now() - interval '1 day' and (%s::uuid is null or id = %s::uuid)
               order by critical desc, created_at""",
            (MAX_ATTEMPTS, only, only),
        )
    ).fetchall()
    counts = {"sent": 0, "failed": 0, "held": 0, "suppressed": 0}
    for a in rows:
        d = await _decision(conn, a, now)
        if d == "hold":
            counts["held"] += 1
            continue
        if d == "suppress":
            await conn.execute("update alerts set status = 'suppressed' where id = %s", (a["id"],))
            counts["suppressed"] += 1
            continue
        subs = await (
            await conn.execute("select * from push_subscriptions where user_id = %s", (a["user_id"],))
        ).fetchall()
        ok = False
        for sub in subs:
            ok = await push.send(sub, message(a), urgent=a["critical"], conn=conn) or ok
        if ok:
            await conn.execute("update alerts set status = 'sent', sent_at = now() where id = %s", (a["id"],))
            counts["sent"] += 1
        else:
            attempts = a["attempts"] + 1
            status = "failed" if attempts >= MAX_ATTEMPTS or not subs else "pending"
            await conn.execute(
                "update alerts set attempts = %s, status = %s where id = %s", (attempts, status, a["id"])
            )
            counts["failed"] += 1
    return counts


async def run() -> None:
    async with await connect() as conn:
        counts = await send_pending(conn)
    if any(counts.values()):
        log.info("outbox: %s", counts)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run_async(run())


if __name__ == "__main__":
    main()
