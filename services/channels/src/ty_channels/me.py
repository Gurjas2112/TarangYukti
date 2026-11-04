"""Personal endpoints (login required): onboarding, preferences, push subscriptions and "Add this phone".

Every query runs as the caller under RLS (`ty_common.db.user_tx`); only the phone link uses the service role,
to mint a one-time sign-in token for the caller's own account (spec §9.1.3, otp_expiry = 600 s).
Responses are `Cache-Control: private, no-store`.
"""

from __future__ import annotations

from datetime import time
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from ty_common.auth import require
from ty_common.db import user_tx
from ty_common.phrases import available_languages, harbours, nearest_language, phrases
from ty_common.settings import get_settings

from . import limits

router = APIRouter()
NO_STORE = "private, no-store"
Purpose = Literal["location_alerts", "family_sharing", "voice_processing"]
BoatKind = Literal["non_motorised", "small_frp", "mechanised_trawler"]
signed_in = require()
Claims = Annotated[dict[str, Any], Depends(signed_in)]


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = NO_STORE


def _check_lang(code: str) -> None:
    if code not in {x["code"] for x in available_languages()}:
        raise HTTPException(422, "language not available")


def _check_harbour(hid: str) -> None:
    if hid not in harbours():
        raise HTTPException(422, "unknown harbour")


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class OnboardIn(Strict):
    language: str
    harbour: str
    boat_kind: BoatKind
    boat_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] | None = None
    consents: list[Purpose] = Field(min_length=1)
    notice_version: str = Field(max_length=20)


@router.post("/onboarding")
async def onboarding(body: OnboardIn, claims: Claims, response: Response) -> dict[str, Any]:
    """Voice onboarding result (spec §7.4): language, harbour, boat and spoken consent, in one transaction."""
    _no_store(response)
    _check_lang(body.language)
    _check_harbour(body.harbour)
    if body.notice_version != phrases(body.language)[0]["consent"]["notice_version"]:
        raise HTTPException(409, "the consent notice changed, please read it again")
    uid = claims["sub"]
    async with user_tx(claims) as cur:
        await cur.execute(
            """insert into user_prefs (user_id, language, home_harbour) values (%s, %s, %s)
               on conflict (user_id) do update
               set language = excluded.language, home_harbour = excluded.home_harbour""",
            (uid, body.language, body.harbour),
        )
        await cur.execute("insert into user_roles (user_id) values (%s) on conflict do nothing", (uid,))
        await cur.execute("select id from boats where owner_id = %s order by created_at limit 1", (uid,))
        row = await cur.fetchone()
        if row is None:
            name = body.boat_name or harbours()[body.harbour]["name"]
            await cur.execute(
                "insert into boats (owner_id, name, kind, home_harbour) values (%s, %s, %s, %s) returning id",
                (uid, name, body.boat_kind, body.harbour),
            )
            row = await cur.fetchone()
        else:
            await cur.execute(
                "update boats set kind = %s, home_harbour = %s where id = %s",
                (body.boat_kind, body.harbour, row["id"]),
            )
        for purpose in dict.fromkeys(body.consents):
            await cur.execute(
                "insert into consents (user_id, purpose, notice_version, language) values (%s, %s, %s, %s)",
                (uid, purpose, body.notice_version, body.language),
            )
            await cur.execute(
                "select public.audit('consent.given', %s, jsonb_build_object('notice', %s::text))",
                (purpose, body.notice_version),
            )
    assert row is not None
    return {"boat_id": str(row["id"])}


@router.get("/me")
async def me(claims: Claims, response: Response) -> dict[str, Any]:
    _no_store(response)
    async with user_tx(claims) as cur:
        await cur.execute(
            "select mode, language, home_harbour, brief_time, quiet_from, quiet_to from user_prefs where user_id = %s",
            (claims["sub"],),
        )
        prefs = await cur.fetchone()
        await cur.execute("select role from user_roles where user_id = %s", (claims["sub"],))
        role = await cur.fetchone()
        await cur.execute("select id, name, kind, home_harbour from boats where owner_id = %s", (claims["sub"],))
        boats = await cur.fetchall()
        await cur.execute(
            "select purpose, notice_version, language, given_at, withdrawn_at from consents order by given_at desc"
        )
        consents = await cur.fetchall()
        await cur.execute("select kind, created_at, last_ok_at from push_subscriptions")
        subs = await cur.fetchall()
        await cur.execute("select delete_after from deletion_requests where user_id = %s", (claims["sub"],))
        deletion = await cur.fetchone()

    def _t(v: Any) -> Any:
        return v.strftime("%H:%M") if isinstance(v, time) else v

    return {
        "prefs": {k: _t(v) for k, v in prefs.items()} if prefs else None,
        "role": role["role"] if role else None,
        "boats": [{**b, "id": str(b["id"])} for b in boats],
        "consents": consents,
        "push": subs,
        "deleting_after": deletion["delete_after"] if deletion else None,
    }


HHMM = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


class PrefsIn(Strict):
    mode: Literal["simple", "expert"] | None = None
    language: str | None = None
    home_harbour: str | None = None
    brief_time: HHMM | None = None
    quiet_from: HHMM | None = None
    quiet_to: HHMM | None = None


@router.put("/me/prefs")
async def put_prefs(body: PrefsIn, claims: Claims, response: Response) -> dict[str, str]:
    _no_store(response)
    fields = body.model_dump(exclude_none=True)
    if "language" in fields:
        _check_lang(fields["language"])
    if "home_harbour" in fields:
        _check_harbour(fields["home_harbour"])
    if not fields:
        return {"status": "unchanged"}
    cols = ", ".join(fields)
    vals = ", ".join(["%s"] * len(fields))
    upd = ", ".join(f"{k} = excluded.{k}" for k in fields)
    async with user_tx(claims) as cur:
        await cur.execute(
            f"insert into user_prefs (user_id, {cols}) values (%s, {vals}) on conflict (user_id) do update set {upd}",
            (claims["sub"], *fields.values()),
        )
    return {"status": "saved"}


class SubscribeIn(Strict):
    kind: Literal["web", "expo"]
    endpoint: str = Field(max_length=1000)
    p256dh: str | None = Field(default=None, max_length=200)
    auth: str | None = Field(default=None, max_length=100)
    user_agent: str | None = Field(default=None, max_length=300)


@router.post("/push/subscribe")
async def subscribe(body: SubscribeIn, claims: Claims, request: Request, response: Response) -> dict[str, str]:
    """Called only after the user taps "Turn on alerts". Sends the test push "alerts are on" through the worker."""
    _no_store(response)
    await limits.check(request, claims, bucket="push")
    if body.kind == "expo" and not body.endpoint.startswith("ExponentPushToken["):
        raise HTTPException(422, "not an Expo push token")
    if body.kind == "web" and not (body.endpoint.startswith("https://") and body.p256dh and body.auth):
        raise HTTPException(422, "web push needs endpoint, p256dh and auth")
    uid = claims["sub"]
    async with user_tx(claims) as cur:
        # an endpoint belongs to one browser/phone: re-subscribing moves it to the signed-in user
        await cur.execute("delete from push_subscriptions where endpoint = %s", (body.endpoint,))
        try:
            async with cur.connection.transaction():
                await cur.execute(
                    """insert into push_subscriptions (user_id, kind, endpoint, p256dh, auth, user_agent)
                       values (%s, %s, %s, %s, %s, %s)""",
                    (uid, body.kind, body.endpoint, body.p256dh, body.auth, body.user_agent),
                )
        except UniqueViolation as e:
            raise HTTPException(409, "this device gets alerts for another account; sign out there first") from e
        await cur.execute("select language from user_prefs where user_id = %s", (uid,))
        pref = await cur.fetchone()
        lang = (pref or {}).get("language") or nearest_language(
            request.headers.get("accept-language", "").split(",")[0]
        )
        p, used = phrases(lang)
        await cur.execute(
            """insert into alerts (user_id, kind, rule, title, body, lang)
               values (%s, 'test', 'push-test', %s, %s, %s)""",
            (uid, "Kadal Mitra", p["push_test"], used),
        )
    return {"status": "subscribed"}


class UnsubscribeIn(Strict):
    endpoint: str = Field(max_length=1000)


@router.post("/push/unsubscribe")
async def unsubscribe(body: UnsubscribeIn, claims: Claims, response: Response) -> dict[str, str]:
    _no_store(response)
    async with user_tx(claims) as cur:
        await cur.execute("delete from push_subscriptions where endpoint = %s", (body.endpoint,))
    return {"status": "removed"}


@router.post("/phone-link")
async def phone_link(claims: Claims, request: Request, response: Response) -> dict[str, Any]:
    """ "Add this phone": a one-time token (10 minutes) that signs the phone into the caller's own account.
    The QR holds `tarangyukti://link?token_hash=…`; the app calls supabase.auth.verifyOtp({token_hash, type})."""
    _no_store(response)
    await limits.check(request, claims, bucket="link")
    email = claims.get("email")
    if not email:
        raise HTTPException(422, "this account has no e-mail address")
    s = get_settings()
    if s.supabase_service_role_key is None:
        raise HTTPException(503, "phone linking is not configured")
    k = s.supabase_service_role_key.get_secret_value()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{s.supabase_url}/auth/v1/admin/generate_link",
            json={"type": "magiclink", "email": email},
            headers={"apikey": k, "Authorization": f"Bearer {k}"},
        )
    if r.status_code >= 400:
        raise HTTPException(502, "could not create a link")
    token_hash = r.json().get("hashed_token") or r.json().get("properties", {}).get("hashed_token")
    if not token_hash:
        raise HTTPException(502, "could not create a link")
    return {
        "token_hash": token_hash,
        "type": "magiclink",
        "expires_in": 600,
        "qr": f"tarangyukti://link?token_hash={token_hash}&type=magiclink",
    }
