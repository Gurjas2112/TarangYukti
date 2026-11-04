"""Nightly housekeeping and the officer warning areas (spec §8.5, §8.4, §9.1, §9.4).

- delete_accounts: deletion requests past their 7-day undo → the account's conversation threads are deleted with
  LangGraph's delete_thread, then the auth user is deleted through the Supabase admin API (every personal table
  cascades). The audit log keeps a salted reference, never the e-mail.
- retention: raw positions older than 30 days → per-day H3 res-7 cell counts with no user id, then deleted;
  answers older than 180 days deleted in Postgres and Neo4j.
- refresh_warning_areas: active official warning polygons (IMD, INCOIS, SDMA) → public.warning_areas, which the
  officer RLS policy and the admin live map use.

    uv run python -m ty_worker.housekeeping [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

import h3
import httpx
import psycopg
from ty_common.settings import get_settings

from . import outbox
from .runtime import run_async

log = logging.getLogger(__name__)
POSITION_DAYS = 30
ANSWER_DAYS = 180


def _ref(user_id: str) -> str:
    return hashlib.sha256(f"ty-deleted:{user_id}".encode()).hexdigest()[:16]


async def delete_accounts(conn: psycopg.AsyncConnection[dict[str, Any]], dry_run: bool = False) -> int:
    rows = await (await conn.execute("select user_id from deletion_requests where delete_after <= now()")).fetchall()
    if dry_run or not rows:
        return len(rows)
    s = get_settings()
    if s.supabase_service_role_key is None:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is needed to delete accounts")
    k = s.supabase_service_role_key.get_secret_value()
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row

    assert s.worker_database_url is not None
    agent_conn = await psycopg.AsyncConnection.connect(
        s.worker_database_url.get_secret_value(),
        autocommit=True,
        row_factory=dict_row,
        prepare_threshold=None,
        options="-c search_path=agent",
    )
    saver = AsyncPostgresSaver(agent_conn)
    done = 0
    for r in rows:
        uid = str(r["user_id"])
        threads = await (
            await conn.execute("select thread_id from agent.threads where user_id = %s", (uid,))
        ).fetchall()
        for t in threads:
            await saver.adelete_thread(t["thread_id"])
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.delete(
                f"{s.supabase_url}/auth/v1/admin/users/{uid}", headers={"apikey": k, "Authorization": f"Bearer {k}"}
            )
        if resp.status_code >= 400 and resp.status_code != 404:
            log.warning("account deletion failed (%s); will retry tomorrow", resp.status_code)
            continue
        await conn.execute(
            "insert into audit_log (action, target, detail) values ('account.deleted', %s, %s::jsonb)",
            (_ref(uid), json.dumps({"threads": len(threads)})),
        )
        done += 1
    await agent_conn.close()
    return done


async def retention(conn: psycopg.AsyncConnection[dict[str, Any]], dry_run: bool = False) -> dict[str, int]:
    old = await (
        await conn.execute(
            """select (recorded_at at time zone 'UTC')::date as day,
                      extensions.st_y(geom::extensions.geometry) as lat,
                      extensions.st_x(geom::extensions.geometry) as lon
               from positions where recorded_at < now() - make_interval(days => %s)""",
            (POSITION_DAYS,),
        )
    ).fetchall()
    cells: dict[tuple[Any, str], int] = {}
    for p in old:
        key = (p["day"], h3.latlng_to_cell(float(p["lat"]), float(p["lon"]), 7))
        cells[key] = cells.get(key, 0) + 1
    out = {"positions_aggregated": len(old), "cells": len(cells), "answers_deleted": 0, "ledgers_deleted": 0}
    if dry_run:
        return out
    for (day, cell), n in cells.items():
        await conn.execute(
            """insert into position_cells (day, cell, fixes) values (%s, %s, %s)
               on conflict (day, cell) do update set fixes = position_cells.fixes + excluded.fixes""",
            (day, cell, n),
        )
    await conn.execute("delete from positions where recorded_at < now() - make_interval(days => %s)", (POSITION_DAYS,))
    cur = await conn.execute("delete from answers where created_at < now() - make_interval(days => %s)", (ANSWER_DAYS,))
    out["answers_deleted"] = cur.rowcount
    try:
        from tarangyukti import ledger

        out["ledgers_deleted"] = await ledger.purge(ANSWER_DAYS)
    except Exception as e:  # Neo4j down: try again tomorrow
        log.warning("ledger purge failed: %s", type(e).__name__)
    return out


async def refresh_warning_areas(conn: psycopg.AsyncConnection[dict[str, Any]]) -> int:
    from tarangyukti.tools import warnings

    found: list[dict[str, Any]] = []
    for fn in (warnings.imd_warnings, warnings.incois_alerts, warnings.sdma_alerts):
        r = await fn()
        found += [w for w in r.get("data", {}).get("warnings", []) if w.get("area")]
    for w in found:
        area = w["area"]
        if area.get("type") == "Polygon":
            area = {"type": "MultiPolygon", "coordinates": [area["coordinates"]]}
        await conn.execute(
            """insert into warning_areas (id, issuer, title, geom, valid_from, valid_to, updated_at)
               values (%s, %s, %s, extensions.st_geomfromgeojson(%s)::extensions.geography, %s, %s, now())
               on conflict (id) do update set title = excluded.title, geom = excluded.geom,
                 valid_from = excluded.valid_from, valid_to = excluded.valid_to, updated_at = now()""",
            (w["id"], w["issuer"], w["title"][:300], json.dumps(area), w["valid_from"], w["valid_to"]),
        )
    await conn.execute("delete from warning_areas where valid_to < now() - interval '1 day'")
    return len(found)


async def run(dry_run: bool = False) -> dict[str, Any]:
    async with await outbox.connect() as conn:
        out: dict[str, Any] = {"accounts_deleted": await delete_accounts(conn, dry_run)}
        out |= await retention(conn, dry_run)
    out["at"] = datetime.now(UTC).isoformat()
    log.info("housekeeping: %s", out)
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(prog="ty_worker.housekeeping")
    ap.add_argument("--dry-run", action="store_true")
    print(run_async(run(ap.parse_args().dry_run)))


if __name__ == "__main__":
    main()
