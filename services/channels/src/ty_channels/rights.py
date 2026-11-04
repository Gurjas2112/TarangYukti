"""User rights and provenance (spec §9.1, §9.4 DPDP, §10.3, §13):

- GET  /me/export          everything we hold about the caller, as JSON (no other user's data; push keys omitted)
- POST /me/delete          request deletion: 7-day undo, then the worker deletes the account and everything cascades
- DELETE /me/delete        undo within the 7 days
- GET  /help               grievance officer and response times (config/governance.yaml)
- GET  /sources/answer/{id}  an answer with its Constraint Ledger — its owner, or staff with MFA (RLS decides)
Every request is written to the audit log as the caller.
"""

from __future__ import annotations

import functools
import json
from typing import Annotated, Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Response
from ty_common.db import user_tx
from ty_common.settings import find_config_dir

from .me import signed_in
from .public import PUBLIC_CACHE, call_tool

router = APIRouter()
Claims = Annotated[dict[str, Any], Depends(signed_in)]
NO_STORE = "private, no-store"

EXPORT = {
    "prefs": "select * from user_prefs where user_id = %(uid)s",
    "roles": "select role from user_roles where user_id = %(uid)s",
    "boats": "select * from boats where owner_id = %(uid)s",
    "trips": "select t.* from trips t join boats b on b.id = t.boat_id where b.owner_id = %(uid)s",
    "positions": """select p.recorded_at, p.speed_knots, p.source,
                           extensions.st_y(p.geom::extensions.geometry) as lat,
                           extensions.st_x(p.geom::extensions.geometry) as lon
                    from positions p join boats b on b.id = p.boat_id where b.owner_id = %(uid)s
                    order by p.recorded_at""",
    "consents": "select * from consents where user_id = %(uid)s",
    "share_grants": """select g.id, g.boat_id, g.grantee_email, g.expires_at, g.revoked_at, g.created_at
                       from share_grants g join boats b on b.id = g.boat_id where b.owner_id = %(uid)s""",
    "push_subscriptions": """select kind, created_at, last_ok_at, user_agent
                             from push_subscriptions where user_id = %(uid)s""",
    "alerts": "select kind, rule, title, body, lang, status, created_at, sent_at from alerts where user_id = %(uid)s",
    "answers": """select created_at, lang, mode, question, reply, verdict, model, prompt_version, config_version
                  from answers where user_id = %(uid)s order by created_at""",
    "deletion_request": "select * from deletion_requests where user_id = %(uid)s",
}


@router.get("/me/export")
async def export(claims: Claims, response: Response) -> Response:
    uid = claims["sub"]
    out: dict[str, Any] = {"account": {"id": uid, "email": claims.get("email")}}
    async with user_tx(claims) as cur:
        for name, q in EXPORT.items():
            await cur.execute(q, {"uid": uid})
            out[name] = await cur.fetchall()
        await cur.execute("select public.audit('data.exported', %s, '{}'::jsonb)", (uid,))
    body = json.dumps(out, default=str, ensure_ascii=False, indent=2)
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="tarangyukti-my-data.json"', "Cache-Control": NO_STORE},
    )


@router.post("/me/delete")
async def request_delete(claims: Claims, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute(
            """insert into deletion_requests (user_id) values (%s)
               on conflict (user_id) do update set user_id = excluded.user_id returning delete_after""",
            (claims["sub"],),
        )
        row = await cur.fetchone()
        await cur.execute("select public.audit('account.delete_requested', %s, '{}'::jsonb)", (claims["sub"],))
    assert row is not None
    return {"delete_after": row["delete_after"]}


@router.delete("/me/delete")
async def cancel_delete(claims: Claims, response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute("delete from deletion_requests where user_id = %s returning user_id", (claims["sub"],))
        if await cur.fetchone() is None:
            raise HTTPException(404, "no deletion pending")
        await cur.execute("select public.audit('account.delete_cancelled', %s, '{}'::jsonb)", (claims["sub"],))
    return {"status": "cancelled"}


@functools.cache
def _governance() -> dict[str, Any]:
    doc: dict[str, Any] = yaml.safe_load((find_config_dir() / "governance.yaml").read_text(encoding="utf-8"))
    return doc


@router.get("/help")
async def help_page(response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    g = _governance()
    return {
        "grievance_officer": g["grievance_officer"],
        "response_days": g["response_days"],
        "erasure_days": g["erasure_days"],
        "deletion_undo_days": g["deletion_undo_days"],
    }


@router.get("/sources/answer/{answer_id}")
async def answer(answer_id: str, claims: Claims, response: Response) -> dict[str, Any]:
    """The answer row (owner or staff with MFA, by RLS) and its ledger as known when it was given."""
    response.headers["Cache-Control"] = NO_STORE
    async with user_tx(claims) as cur:
        await cur.execute(
            """select id, created_at, lang, mode, question, reply, verdict, ledger_answer_id, citations, guard,
                      fallback, model, prompt_version, config_version
               from answers where id::text = %s or ledger_answer_id = %s
               order by created_at desc limit 1""",
            (answer_id, answer_id),
        )
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(404, "no such answer, or it is not yours")
    ledger = None
    if row["ledger_answer_id"]:
        ledger = (await call_tool("answer_ledger", {"answer_id": row["ledger_answer_id"]})).get("data")
    return {"answer": {**row, "id": str(row["id"])}, "ledger": ledger}
