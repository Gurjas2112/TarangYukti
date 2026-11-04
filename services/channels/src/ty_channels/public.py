"""Public endpoints (no login, rule 7): languages, harbours and the Simple-mode sea card."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Response
from fastmcp import Client
from fastmcp.exceptions import ToolError
from ty_common.phrases import available_languages, harbours, nearest_language, phrases
from ty_common.settings import get_settings

router = APIRouter()
PUBLIC_CACHE = "public, max-age=60, stale-while-revalidate=300"
BoatKind = Literal["non_motorised", "small_frp", "mechanised_trawler"]


@router.get("/languages")
async def languages(response: Response, locale: str | None = None) -> dict[str, Any]:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    keep = ("code", "name", "group", "script", "rtl", "status")
    return {
        "languages": [{k: x[k] for k in keep} for x in available_languages()],
        "suggested": nearest_language(locale) if locale else None,
    }


@router.get("/harbours")
async def harbour_list(response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    keep = ("id", "name", "state", "lat", "lon", "suggested_language")
    return {"harbours": [{k: h[k] for k in keep} for h in harbours().values()]}


async def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    try:
        async with Client(get_settings().mcp_url, timeout=120) as c:
            r = await c.call_tool(name, args)
    except ToolError as e:  # bad input (e.g. a point outside the region): the tool explains why
        raise HTTPException(422, str(e)) from e
    data = r.structured_content
    if not isinstance(data, dict):
        raise HTTPException(502, "data service returned no result")
    inner = data.get("result")
    return inner if isinstance(inner, dict) and len(data) == 1 else data


@router.get("/brief")
async def brief(response: Response, harbour: str, boat_type: BoatKind, lang: str) -> dict[str, Any]:
    if harbour not in harbours():
        raise HTTPException(422, "unknown harbour")
    if lang not in {x["code"] for x in available_languages()}:
        raise HTTPException(422, "language not available")
    card = await call_tool("sea_brief", {"harbour_id": harbour, "boat_type": boat_type, "lang": lang})
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return card


@router.get("/consent")
async def consent(response: Response, lang: str) -> dict[str, Any]:
    """The spoken consent of onboarding (spec §7.4) in approved wording, with its notice version."""
    if lang not in {x["code"] for x in available_languages()}:
        raise HTTPException(422, "language not available")
    p, used = phrases(lang)
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return {**p["consent"], "lang": used, "status": p.get("status", "draft")}
