"""Admin console API (spec §10.3). platform_admin with MFA (aal2) only — checked here from the JWT and again by
each database function. Every action is audit-logged in the database with its reason.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from ty_common.auth import require
from ty_common.db import user_tx
from ty_common.settings import get_settings

from .public import call_tool

router = APIRouter(prefix="/admin")
admin_only = require("platform_admin", mfa=True)
Admin = Annotated[dict[str, Any], Depends(admin_only)]
NO_STORE = "private, no-store"
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


async def _fn(claims: dict[str, Any], sql: str, args: tuple[Any, ...] = ()) -> Any:
    async with user_tx(claims) as cur:
        await cur.execute(sql, args)
        row = await cur.fetchone()
    return next(iter(row.values())) if row else None


@router.get("/overview")
async def overview(claims: Admin, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = NO_STORE
    data: dict[str, Any] = await _fn(claims, "select public.admin_overview()")
    return data


@router.get("/sources")
async def sources(claims: Admin, response: Response) -> dict[str, Any]:
    """Each live source: last fetch, cache state, confidence, notes (age vs freshness limit)."""
    response.headers["Cache-Control"] = NO_STORE
    out = []
    for name, args in [
        ("marine_forecast", {"lat": 9.288, "lon": 79.313, "hours": 1}),  # public harbour position
        ("imd_warnings", {}),
        ("incois_alerts", {}),
        ("sdma_alerts", {}),
        ("pfz_incois", {}),
        ("sst_grid", {}),
        ("chl_grid", {}),
    ]:
        try:
            r = await call_tool(name, args)
            out.append(
                {
                    "tool": name,
                    "source": r.get("source"),
                    "fetched_at": r.get("fetched_at"),
                    "cache": r.get("cache"),
                    "confidence": r.get("confidence"),
                    "available": r.get("data", {}).get("available", True),
                    "notes": r.get("notes", [])[:4],
                }
            )
        except HTTPException as e:
            out.append({"tool": name, "available": False, "notes": [str(e.detail)]})
    return {"sources": out}


@router.get("/alerts")
async def alerts(claims: Admin, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = NO_STORE
    return {"alerts": await _fn(claims, "select public.admin_alerts(200)")}


@router.post("/alerts/{alert_id}/retry")
async def retry(alert_id: str, claims: Admin) -> dict[str, str]:
    await _fn(claims, "select public.admin_retry_alert(%s::uuid)", (alert_id,))
    return {"status": "queued"}


@router.get("/users")
async def users(claims: Admin, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = NO_STORE
    return {"users": await _fn(claims, "select public.admin_users()")}


class RoleIn(Strict):
    role: Literal["fisher", "family", "analyst", "officer", "platform_admin"]
    reason: Reason


@router.post("/users/{user_id}/role")
async def set_role(user_id: str, body: RoleIn, claims: Admin) -> dict[str, str]:
    if user_id == claims["sub"] and body.role != "platform_admin":
        raise HTTPException(422, "you cannot remove your own admin role")
    await _fn(claims, "select public.set_role(%s::uuid, %s::public.app_role, %s)", (user_id, body.role, body.reason))
    return {"status": "saved"}


class InviteIn(Strict):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=EMAIL)]
    role: Literal["analyst", "officer", "platform_admin"]
    reason: Reason


@router.post("/invite")
async def invite(body: InviteIn, claims: Admin) -> dict[str, str]:
    """Invite staff by e-mail (Supabase sends the invitation); the role applies once they sign in with Google
    and enrol MFA."""
    s = get_settings()
    if s.supabase_service_role_key is None:
        raise HTTPException(503, "invitations are not configured")
    k = s.supabase_service_role_key.get_secret_value()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            f"{s.supabase_url}/auth/v1/invite",
            json={"email": body.email},
            headers={"apikey": k, "Authorization": f"Bearer {k}"},
        )
    if r.status_code >= 400 and "already" not in r.text.lower():
        raise HTTPException(502, "invitation failed")
    uid = r.json().get("id") if r.status_code < 400 else None
    if uid is None:  # existing account: look it up among users
        found = [u for u in (await _fn(claims, "select public.admin_users()")) or [] if u["email"] == body.email]
        if not found:
            raise HTTPException(502, "invitation failed")
        uid = found[0]["id"]
    await _fn(claims, "select public.set_role(%s::uuid, %s::public.app_role, %s)", (uid, body.role, body.reason))
    return {"status": "invited", "user_id": str(uid)}


@router.get("/live")
async def live(claims: Admin, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = NO_STORE
    return {"cells": await _fn(claims, "select public.admin_live_cells()")}


@router.get("/kb")
async def kb(claims: Admin, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute(
            """select d.id, d.source_id, d.version, d.issuer, d.doc_type, d.status, d.valid_to, d.ingested_at,
                      d.superseded_by, d.superseded_at, (select count(*) from kb_chunks c where c.document_id = d.id)
                      as chunks
               from kb_documents d order by d.status desc, d.ingested_at desc"""
        )
        docs = await cur.fetchall()
    return {"documents": [{**d, "id": str(d["id"])} for d in docs]}


class KbDecision(Strict):
    approve: bool
    reason: Reason


@router.post("/kb/{doc_id}/decide")
async def kb_decide(doc_id: str, body: KbDecision, claims: Admin) -> dict[str, str]:
    await _fn(claims, "select public.admin_kb_decide(%s::uuid, %s, %s)", (doc_id, body.approve, body.reason))
    return {"status": "approved" if body.approve else "rejected"}


class Supersede(Strict):
    by: str = Field(min_length=36, max_length=36)
    reason: Reason


@router.post("/kb/{doc_id}/supersede")
async def kb_supersede(doc_id: str, body: Supersede, claims: Admin) -> dict[str, str]:
    await _fn(claims, "select public.admin_kb_supersede(%s::uuid, %s::uuid, %s)", (doc_id, body.by, body.reason))
    return {"status": "superseded"}


@router.get("/guardrails")
async def guardrails(claims: Admin, response: Response) -> dict[str, Any]:
    """Answers the validator blocked, rewrote or replaced with a template (staff policy on answers)."""
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute(
            """select id, created_at, lang, mode, question, reply, guard, fallback, model, prompt_version, citations
               from answers
               where coalesce((guard->>'ungrounded_number')::int, 0) > 0
                  or coalesce((guard->>'quote_dropped')::int, 0) > 0
                  or coalesce((guard->>'template_fallback')::boolean, false)
                  or coalesce((guard->>'language_mismatch')::boolean, false)
                  or coalesce((guard->>'rewritten')::boolean, false)
               order by created_at desc limit 100"""
        )
        rows = await cur.fetchall()
    return {"answers": [{**r, "id": str(r["id"])} for r in rows]}


class FailureIn(Strict):
    answer_id: str | None = Field(default=None, min_length=36, max_length=36)
    wrong: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
    expect: Annotated[str, StringConstraints(max_length=500)] | None = None


@router.post("/failures")
async def add_failure(body: FailureIn, claims: Admin) -> dict[str, Any]:
    """Guardrail review → "Add to failures dataset". `make failures-pull` turns these into failures.yaml rows (PR)."""
    async with user_tx(claims) as cur:
        await cur.execute(
            """insert into failure_candidates (answer_id, wrong, expect, created_by) values (%s, %s, %s, %s)
               returning id""",
            (body.answer_id, body.wrong, body.expect, claims["sub"]),
        )
        row = await cur.fetchone()  # the candidate row itself records who added it and when
    assert row is not None
    return {"id": row["id"]}


@router.get("/audit")
async def audit(claims: Admin, response: Response, action: str | None = None, limit: int = 200) -> dict[str, Any]:
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute(
            """select id, at, action, target, detail, row_hash,
                      left(encode(extensions.digest(coalesce(actor::text, ''), 'sha256'), 'hex'), 10) as actor_ref
               from audit_log where (%s::text is null or action = %s) order by id desc limit %s""",
            (action, action, min(max(limit, 1), 1000)),
        )
        rows = await cur.fetchall()
    return {"events": rows}


@router.post("/audit/verify")
async def verify(claims: Admin) -> dict[str, Any]:
    broken = await _fn(claims, "select public.audit_verify()")
    return {"intact": broken is None, "first_broken_id": broken}


class FlagIn(Strict):
    value: bool | list[str]
    reason: Reason


@router.post("/flags/{key}")
async def set_flag(key: Literal["free_chat_off", "alerts_paused"], body: FlagIn, claims: Admin) -> dict[str, str]:
    if key == "free_chat_off" and not isinstance(body.value, bool):
        raise HTTPException(422, "free_chat_off takes true or false")
    if key == "alerts_paused" and not isinstance(body.value, list):
        raise HTTPException(422, "alerts_paused takes a list of harbour ids")
    await _fn(claims, "select public.set_flag(%s, %s::jsonb, %s)", (key, json.dumps(body.value), body.reason))
    return {"status": "saved"}


@router.get("/replay/{answer_id}")
async def replay(answer_id: str, claims: Admin, response: Response) -> dict[str, Any]:
    from .rights import answer

    return await answer(answer_id, claims, response)
