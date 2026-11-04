"""Family notice and the border safety net (prompt §10.5, spec §6.6).

- notify_family: every closed trip not yet announced → one "… is back at …, HH:MM" push to each holder of a valid
  share grant, in that person's language. The boat name is added here, at send time (never cached).
- sweep_border: boats with an open trip and a position in the last 30 minutes are checked against the border line
  and the marine park with the same rules channels applies on every live fix — the safety net if a check was missed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import psycopg
from tarangyukti.tools.geo import fence_check
from ty_common import trips as rules
from ty_common.phrases import harbours, nearest_language, text

log = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

CLOSED = """
select t.id, t.returned_at, b.id as boat_id, b.name, b.home_harbour
from trips t join boats b on b.id = t.boat_id
where t.returned_at is not null and t.family_notified_at is null and t.returned_at > now() - interval '12 hours'
"""
GRANTEES = """
select g.grantee_id, p.language
from share_grants g left join user_prefs p on p.user_id = g.grantee_id
where g.boat_id = %s and g.grantee_id is not null and g.revoked_at is null and g.expires_at > now()
"""


async def notify_family(conn: psycopg.AsyncConnection[dict[str, Any]]) -> int:
    sent = 0
    for t in await (await conn.execute(CLOSED)).fetchall():
        h = harbours().get(t["home_harbour"] or "")
        when = t["returned_at"].astimezone(IST).strftime("%H:%M")
        for g in await (await conn.execute(GRANTEES, (t["boat_id"],))).fetchall():
            lang = g["language"] or nearest_language(None)
            title, _ = text(lang, "family_title")
            body, used = text(lang, "back_home", name=t["name"], harbour=h["name"] if h else "", time=when)
            await conn.execute(
                """insert into alerts (user_id, boat_id, kind, rule, title, body, lang, url)
                   values (%s, %s, 'family', 'trip-back', %s, %s, %s, %s)""",
                (g["grantee_id"], t["boat_id"], title, body, used, f"/family/{t['boat_id']}"),
            )
            sent += 1
        await conn.execute("update trips set family_notified_at = now() where id = %s", (t["id"],))
    return sent


LIVE = """
select distinct on (p.boat_id) p.boat_id, b.owner_id,
       extensions.st_y(p.geom::extensions.geometry) as lat, extensions.st_x(p.geom::extensions.geometry) as lon,
       pr.language
from positions p
join boats b on b.id = p.boat_id
join trips t on t.boat_id = p.boat_id and t.returned_at is null
left join user_prefs pr on pr.user_id = b.owner_id
where p.recorded_at > now() - interval '30 minutes'
order by p.boat_id, p.recorded_at desc
"""


async def sweep_border(conn: psycopg.AsyncConnection[dict[str, Any]], now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    queued = 0
    for b in await (await conn.execute(LIVE)).fetchall():
        try:
            fence = fence_check(float(b["lat"]), float(b["lon"]))["data"]
        except Exception:
            log.warning("sweep: fence check failed for one boat")
            continue
        fired = rules.fence_rules(float(fence["imbl_km"]), fence["side"] == "beyond_imbl", bool(fence["in_mpa"]))
        if not fired:
            continue
        rows = await (
            await conn.execute(
                "select rule, created_at from alerts where boat_id = %s and kind = 'alert' and created_at > %s",
                (b["boat_id"], now - rules.REPEAT_GAP),
            )
        ).fetchall()
        recent = [rules.Sent(r["rule"], r["created_at"]) for r in rows]
        lang = b["language"] or nearest_language(None)
        for rule in fired:
            if not rules.should_alert(rule, now, recent):
                continue
            title, _ = text(lang, "alerts.title")
            body, used = text(lang, f"alerts.{rule}", distance_km=round(float(fence["imbl_km"]), 1))
            await conn.execute(
                """insert into alerts (user_id, boat_id, kind, rule, critical, title, body, lang, url)
                   values (%s, %s, 'alert', %s, %s, %s, %s, %s, '/alerts')""",
                (b["owner_id"], b["boat_id"], rule, rule != "mpa", title, body, used),
            )
            recent.append(rules.Sent(rule, now))
            queued += 1
    return queued
