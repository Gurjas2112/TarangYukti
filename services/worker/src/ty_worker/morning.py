"""Morning brief (prompt §10.1, spec §7.3 row 1 and §7.8).

Each signed-in fisher with a boat and a push subscription gets one brief a day, 30 minutes before their usual
departure (median of the last 10 trips; default 04:00 IST), or at user_prefs.brief_time when set. The card is
the shared Simple-mode sea card for (harbour, boat type, language) — approved phrases only — and the push holds
its headline and first reason. Personal details are added here, at send time, never in the shared card.

    uv run python -m ty_worker.morning --user <uuid>     # make brief-now USER=<uuid>: send one now
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import psycopg
from tarangyukti.brief import sea_brief
from ty_common.phrases import harbour, nearest_language, phrases

from . import budget, outbox
from .runtime import run_async

log = logging.getLogger(__name__)
LATE_LIMIT = timedelta(hours=2)  # a brief more than 2 h late is skipped (the fisher has left)

CANDIDATES = """
select p.user_id, p.language, coalesce(p.home_harbour, b.home_harbour) as harbour, p.brief_time,
       b.id as boat_id, b.kind as boat_kind,
       array(select (t.departed_at at time zone 'Asia/Kolkata')::time from trips t
             where t.boat_id = b.id order by t.departed_at desc limit 10) as departures
from user_prefs p
join user_roles r on r.user_id = p.user_id and r.role = 'fisher'
join lateral (select * from boats where owner_id = p.user_id order by created_at limit 1) b on true
where exists (select 1 from push_subscriptions s where s.user_id = p.user_id)
  and (%(user)s::uuid is null or p.user_id = %(user)s::uuid)
"""


async def queue_brief(conn: psycopg.AsyncConnection[dict[str, Any]], u: dict[str, Any]) -> str | None:
    lang = u["language"] or nearest_language(None)
    hid = u["harbour"] or home_harbour_id()
    card = await sea_brief(hid, u["boat_kind"], lang)
    p, used = phrases(lang)
    body = " ".join([card["headline"], *card["why"][:1]])[:480]
    url = "/brief?" + urlencode({"harbour": hid, "boat": u["boat_kind"], "lang": used})
    row = await (
        await conn.execute(
            """insert into alerts (user_id, boat_id, kind, rule, title, body, lang, answer_id, url)
               values (%s, %s, 'brief', 'brief', %s, %s, %s, %s, %s) returning id""",
            (
                u["user_id"],
                u["boat_id"],
                p["brief_title"].format(harbour=harbour(hid)["name"]),
                body,
                used,
                card.get("answer_id"),
                url,
            ),
        )
    ).fetchone()
    log.info("brief queued for harbour %s (%s, %s): %s", hid, u["boat_kind"], used, card["verdict"])
    return str(row["id"]) if row else None


def home_harbour_id() -> str:
    """The region's default harbour (config/qc.yaml); onboarding always stores one, so this is only a guard."""
    from tarangyukti import config

    return str(config.qc()["region"]["home_harbour"]["id"])


async def due_users(conn: psycopg.AsyncConnection[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    rows = await (await conn.execute(CANDIDATES, {"user": None})).fetchall()
    out = []
    for u in rows:
        due = budget.brief_due_at(now, u["brief_time"], list(u["departures"] or []))
        if not (due <= now < due + LATE_LIMIT):
            continue
        sent = await (
            await conn.execute(
                "select 1 from alerts where user_id = %s and kind = 'brief' and created_at >= %s",
                (u["user_id"], budget.ist_day_start(now)),
            )
        ).fetchone()
        if sent is None:
            out.append(u)
    return out


async def run(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    async with await outbox.connect() as conn:
        users = await due_users(conn, now)
        for u in users:
            try:
                await queue_brief(conn, u)
            except Exception:
                log.exception("brief failed for one user")
        if users:
            await outbox.send_pending(conn)
    return len(users)


async def brief_now(user_id: str) -> dict[str, int]:
    async with await outbox.connect() as conn:
        rows = await (await conn.execute(CANDIDATES, {"user": user_id})).fetchall()
        if not rows:
            raise SystemExit("no such fisher with a boat and a push subscription (finish onboarding + Turn on alerts)")
        aid = await queue_brief(conn, rows[0])
        return await outbox.send_pending(conn, only=aid)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(prog="ty_worker.morning")
    ap.add_argument("--user", help="send this user's brief now (make brief-now USER=<uuid>)")
    a = ap.parse_args()
    if a.user:
        print(run_async(brief_now(a.user)))
    else:
        print(f"briefs queued: {run_async(run())}")


if __name__ == "__main__":
    main()
