"""Live positions, trips, feedback and family sharing (prompt §10.5-10.7, spec §6.6, §9.1.3). Login required.

POST /positions takes up to 100 fixes (the web build sends one a minute while open; the Android outbox syncs a
batch). Each batch is stored under RLS, then checked at once: leaving the harbour circle opens a trip, re-entering
closes it; the newest fix is checked against the border line and the marine park, and border alerts are queued
for the worker (one sender) in the user's language. Responses never echo coordinates back to other users.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from ty_common import trips as rules
from ty_common.db import user_tx
from ty_common.phrases import harbour as harbour_info
from ty_common.phrases import harbours, nearest_language, text

from . import limits
from .me import signed_in
from .public import call_tool

router = APIRouter()
Claims = Annotated[dict[str, Any], Depends(signed_in)]
NO_STORE = "private, no-store"
FUTURE_SLACK = timedelta(minutes=2)
MAX_AGE = timedelta(hours=24)


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class Fix(Strict):
    lat: float = Field(ge=8.0, le=10.5)  # prototype region (Gulf of Mannar + Palk Bay)
    lon: float = Field(ge=78.0, le=80.5)
    recorded_at: datetime
    speed_knots: float | None = Field(default=None, ge=0, le=40)

    model_config = ConfigDict(strict=False, extra="forbid")  # datetimes arrive as ISO strings

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("recorded_at needs a timezone")
        return v.astimezone(UTC)


class PositionsIn(Strict):
    boat_id: str = Field(min_length=36, max_length=36)
    source: Literal["web_live", "mobile_app", "simulated"]
    fixes: list[Fix] = Field(min_length=1, max_length=100)


def check_times(fixes: list[Fix], now: datetime) -> list[Fix]:
    """Reject future timestamps (spec §9.3) and ignore fixes older than a day; return them oldest first."""
    for f in fixes:
        if f.recorded_at > now + FUTURE_SLACK:
            raise HTTPException(422, "recorded_at is in the future")
    kept = sorted((f for f in fixes if now - f.recorded_at <= MAX_AGE), key=lambda f: f.recorded_at)
    if not kept:
        raise HTTPException(422, "all fixes are older than 24 hours")
    return kept


async def _lang(cur: Any, uid: str, request: Request) -> str:
    await cur.execute("select language from user_prefs where user_id = %s", (uid,))
    row = await cur.fetchone()
    return (row or {}).get("language") or nearest_language(request.headers.get("accept-language", "").split(",")[0])


@router.post("/positions")
async def positions(body: PositionsIn, claims: Claims, request: Request, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = NO_STORE
    await limits.check(request, claims, bucket="positions")
    now = datetime.now(UTC)
    fixes = check_times(body.fixes, now)
    uid = claims["sub"]
    events: list[str] = []
    async with user_tx(claims) as cur:
        await cur.execute(
            "select id, name, home_harbour from boats where id = %s and owner_id = %s", (body.boat_id, uid)
        )
        boat = await cur.fetchone()
        if boat is None:
            raise HTTPException(404, "no such boat")
        for f in fixes:
            await cur.execute(
                """insert into positions (boat_id, geom, speed_knots, recorded_at, source)
                   values (%s, extensions.st_setsrid(extensions.st_makepoint(%s, %s), 4326)::extensions.geography,
                           %s, %s, %s)""",
                (body.boat_id, f.lon, f.lat, f.speed_knots, f.recorded_at, body.source),
            )
        # trips: replay the batch through the harbour geofence
        h = harbour_info(boat["home_harbour"]) if boat["home_harbour"] in harbours() else None
        await cur.execute(
            "select id, departed_at from trips where boat_id = %s and returned_at is null", (body.boat_id,)
        )
        trip = await cur.fetchone()
        if h is not None:
            for f in fixes:
                move = rules.transition(trip is not None, rules.at_harbour(f.lat, f.lon, h))
                if move == "open":
                    await cur.execute(
                        """select answer_id from alerts where user_id = %s and kind = 'brief'
                           and created_at > %s order by created_at desc limit 1""",
                        (uid, f.recorded_at - timedelta(hours=12)),
                    )
                    brief = await cur.fetchone()
                    await cur.execute(
                        """insert into trips (boat_id, departed_at, advice_answer_id) values (%s, %s, %s)
                           returning id, departed_at""",
                        (body.boat_id, f.recorded_at, (brief or {}).get("answer_id")),
                    )
                    trip = await cur.fetchone()
                    events.append("trip-opened")
                elif move == "close" and trip is not None and f.recorded_at > trip["departed_at"]:
                    await cur.execute(
                        "update trips set returned_at = %s, closed_by = 'geofence' where id = %s",
                        (f.recorded_at, trip["id"]),
                    )
                    trip = None
                    events.append("trip-closed")
        lang = await _lang(cur, uid, request)

    # border and park check on the newest fix (outside the transaction: the MCP call can take a moment)
    last = fixes[-1]
    fence = (await call_tool("fence_check", {"lat": last.lat, "lon": last.lon}))["data"]
    fired = rules.fence_rules(float(fence["imbl_km"]), fence["side"] == "beyond_imbl", bool(fence["in_mpa"]))
    queued: list[str] = []
    if fired and trip is not None:
        async with user_tx(claims) as cur:
            await cur.execute(
                """select rule, created_at from alerts where boat_id = %s and kind = 'alert'
                   and created_at > %s""",
                (body.boat_id, now - rules.REPEAT_GAP),
            )
            recent = [rules.Sent(r["rule"], r["created_at"]) for r in await cur.fetchall()]
            for rule in fired:
                if not rules.should_alert(rule, now, recent):
                    continue
                title, _ = text(lang, "alerts.title")
                msg, used = text(lang, f"alerts.{rule}", distance_km=round(float(fence["imbl_km"]), 1))
                await cur.execute(
                    "select public.queue_boat_alert(%s, %s, %s, %s, %s)", (body.boat_id, rule, title, msg, used)
                )
                recent.append(rules.Sent(rule, now))
                queued.append(rule)
    return {
        "stored": len(fixes),
        "trip": {"id": str(trip["id"]), "departed_at": trip["departed_at"]} if trip else None,
        "events": events,
        "border": {"km": round(float(fence["imbl_km"]), 1), "ring": fence["ring"], "in_marine_park": fence["in_mpa"]},
        "alerts": queued,
    }


@router.get("/trips")
async def trips(claims: Claims, response: Response) -> dict[str, Any]:
    """The open trip, the last 30 closed trips and "right on N of the last M days"."""
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute(
            """select t.id, t.boat_id, t.departed_at, t.returned_at, t.closed_by, t.advice_verdict, t.feedback
               from trips t join boats b on b.id = t.boat_id where b.owner_id = %s
               order by t.departed_at desc limit 31""",
            (claims["sub"],),
        )
        rows = await cur.fetchall()
    open_trip = next((r for r in rows if r["returned_at"] is None), None)
    closed = [r for r in rows if r["returned_at"] is not None][:30]
    right, total = rules.right_on([r["feedback"] for r in closed])

    def out(r: dict[str, Any]) -> dict[str, Any]:
        return {**r, "id": str(r["id"]), "boat_id": str(r["boat_id"])}

    return {
        "open": out(open_trip) if open_trip else None,
        "closed": [out(r) for r in closed],
        "right_on": {"right": right, "total": total},
    }


@router.post("/trips/back")
async def back(claims: Claims, response: Response) -> dict[str, Any]:
    """ "I'm back": close the open trip now (closed_by='button'); the worker tells the family."""
    response.headers["Cache-Control"] = NO_STORE
    now = datetime.now(UTC)
    async with user_tx(claims) as cur:
        await cur.execute(
            """update trips t set returned_at = greatest(%s, t.departed_at + interval '1 second'), closed_by = 'button'
               from boats b where b.id = t.boat_id and b.owner_id = %s and t.returned_at is null
               returning t.id, t.departed_at, t.returned_at""",
            (now, claims["sub"]),
        )
        row = await cur.fetchone()
    if row is None:
        return {"closed": None}
    return {"closed": {"id": str(row["id"]), "departed_at": row["departed_at"], "returned_at": row["returned_at"]}}


class FeedbackIn(Strict):
    feedback: Literal["right", "wrong"]
    note: Annotated[str, StringConstraints(max_length=500)] | None = None


@router.post("/trips/{trip_id}/feedback")
async def feedback(trip_id: str, body: FeedbackIn, claims: Claims, response: Response) -> dict[str, str]:
    """👍/👎 after a closed trip (+ optional note). Thresholds change only by human review, never from this."""
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute(
            """update trips set feedback = %s, feedback_note = %s
               where id = %s and returned_at is not null returning id""",
            (body.feedback, body.note, trip_id),
        )
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(404, "no closed trip with that id")
    return {"status": "saved"}


# ── family sharing


class ShareIn(Strict):
    boat_id: str = Field(min_length=36, max_length=36)
    email: Annotated[
        str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    ]
    days: int = Field(default=90, ge=1, le=90)


@router.post("/share")
async def share(body: ShareIn, claims: Claims, request: Request, response: Response) -> dict[str, Any]:
    """Share a boat with a family member's e-mail for up to 90 days. They see it after signing in with Google."""
    response.headers["Cache-Control"] = NO_STORE
    await limits.check(request, claims, bucket="share")
    if body.email == str(claims.get("email", "")).lower():
        raise HTTPException(422, "that is your own address")
    async with user_tx(claims) as cur:
        await cur.execute(
            """insert into share_grants (boat_id, grantee_email, expires_at)
               values (%s, %s, now() + make_interval(days => %s)) returning id, expires_at""",
            (body.boat_id, body.email, body.days),
        )
        row = await cur.fetchone()
        await cur.execute(
            "select public.audit('share.created', %s, jsonb_build_object('days', %s))", (body.boat_id, body.days)
        )
    assert row is not None
    return {"id": str(row["id"]), "expires_at": row["expires_at"]}


@router.get("/share")
async def my_shares(claims: Claims, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute(
            """select g.id, g.boat_id, g.grantee_email, g.grantee_id is not null as accepted, g.expires_at, g.revoked_at
               from share_grants g join boats b on b.id = g.boat_id where b.owner_id = %s
               order by g.created_at desc""",
            (claims["sub"],),
        )
        rows = await cur.fetchall()
    return {"grants": [{**r, "id": str(r["id"]), "boat_id": str(r["boat_id"])} for r in rows]}


@router.delete("/share/{grant_id}")
async def revoke(grant_id: str, claims: Claims, response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute(
            "update share_grants set revoked_at = now() where id = %s and revoked_at is null returning id", (grant_id,)
        )
        if await cur.fetchone() is None:
            raise HTTPException(404, "no such grant")
        await cur.execute("select public.audit('share.revoked', %s, '{}'::jsonb)", (grant_id,))
    return {"status": "revoked"}


@router.get("/family")
async def family(claims: Claims, response: Response) -> dict[str, Any]:
    """Boats shared with me (claims pending grants for my e-mail first): at sea since / back at, last advice."""
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute("select public.claim_share_grants()")
        await cur.execute(
            """select b.id, b.name, b.home_harbour,
                      t.departed_at, t.returned_at, t.advice_verdict
               from boats b
               left join lateral (select * from trips where boat_id = b.id order by departed_at desc limit 1) t on true
               where b.owner_id <> %s""",
            (claims["sub"],),
        )
        rows = await cur.fetchall()
    out = []
    for r in rows:
        h = harbours().get(r["home_harbour"] or "")
        out.append(
            {
                "boat_id": str(r["id"]),
                "name": r["name"],
                "harbour": h["name"] if h else None,
                "at_sea": r["departed_at"] is not None and r["returned_at"] is None,
                "departed_at": r["departed_at"],
                "returned_at": r["returned_at"],
                "advice_verdict": r["advice_verdict"],
            }
        )
    return {"boats": out}
