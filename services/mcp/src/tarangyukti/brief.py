"""The Simple-mode sea card: the Today screen, the morning brief and the button flows (prompt §10, spec §7.8–7.9).

Everything shown is an approved phrase (config/phrases/<lang>.yaml) with slots filled from tool results:
the verdict and reasons from yukti_evaluate, the 24-hour ribbon from the same engine (one local trip per hour),
the border distance from fence_check and the fishing spot from the INCOIS PFZ points. No LLM, no codes
(PFZ, IMBL, H1–H8) in any sentence. Times are IST "HH:MM".

The card is shared by everyone at one harbour with one boat type and language, so it is cached (`brief`
namespace) under the Yukti input versions + config + phrase versions; names and boat names are added at send
time, never stored here.
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from ty_common.cache import cached, config_version, fingerprint, norm_window30, to_cell
from ty_common.phrases import footer, harbour, phrases, phrases_version

from . import layers
from .tools import geo, yukti_tools
from .yukti import engine, facts
from .yukti.model import Ctx

IST = timezone(timedelta(hours=5, minutes=30))
CODES = ("PFZ", "IMBL", *(f"H{i}" for i in range(1, 9)), *(f"S{i}" for i in range(1, 6)))
_DIRS = ("north", "north_east", "east", "south_east", "south", "south_west", "west", "north_west")


def hhmm(iso_or_dt: str | datetime | None) -> str | None:
    if iso_or_dt is None:
        return None
    t = datetime.fromisoformat(iso_or_dt) if isinstance(iso_or_dt, str) else iso_or_dt
    return f"{t.astimezone(IST):%H:%M}"


def direction_key(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.cos(math.radians(lon2 - lon1))
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    return _DIRS[round(bearing / 45) % 8]


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def reasons(p: dict[str, Any], ev: dict[str, Any] | None) -> list[str]:
    """One approved sentence per failed hard constraint, in ledger order, without duplicates."""
    if not ev:
        return []
    out: list[str] = []
    for e in ev["ledger"]:
        if e["kind"] != "hard" or e["ok"]:
            continue
        tpl = p.get("why", {}).get(e["id"])
        if not tpl:
            continue
        detail = e.get("detail") or ""
        value = e.get("value")
        out.append(
            tpl.format(
                time=hhmm(e.get("at")) or hhmm(ev["depart"]),
                issuer=detail.split(" ")[0] if detail else "official",
                warning_name=value if isinstance(value, str) and value != "unknown" else detail,
            )
        )
    return list(dict.fromkeys(out))


def ribbon(ctx: Ctx, start: str, hours: int = 24) -> list[dict[str, str]]:
    """Outcome of a local trip leaving at each of the next `hours` hours (same engine, same constraints)."""
    t0 = ctx.as_of.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    out = []
    for i in range(hours):
        t = t0 + timedelta(hours=i)
        ev = engine.evaluate(ctx, engine.local_candidate(ctx, start, t))
        out.append({"time": f"{t.astimezone(IST):%H:%M}", "verdict": ev.outcome})
    return out


def spot(ctx: Ctx, lat: float, lon: float, p: dict[str, Any]) -> dict[str, Any] | None:
    if not ctx.pfz_points:
        return None
    dist, plat, plon = min((km(lat, lon, a, b), a, b) for a, b in ctx.pfz_points)
    d = round(dist)
    word = p.get("directions", {}).get(direction_key(lat, lon, plat, plon), "")
    return {"distance_km": d, "text": p["spot"].format(distance_km=d, direction=word).strip()}


def speakable(card: dict[str, Any]) -> str:
    parts = [card["headline"], *card["why"][:1]]
    if card.get("spot"):
        parts.append(card["spot"]["text"])
    parts.append(card["border"]["text"])
    if card.get("stale"):
        parts.append(card["stale"])
    parts.append(card["footer"])
    return " ".join(parts)


@cached(
    ns="brief",
    ttl=900,
    key=lambda parts, ctx, harbour_id, boat_type, lang: fingerprint(*parts),
    tags=lambda parts, ctx, harbour_id, boat_type, lang: [f"harbour:{harbour_id}"],
)
async def _card(parts: list[str], ctx: Ctx, harbour_id: str, boat_type: str, lang: str) -> dict[str, Any]:
    h = harbour(harbour_id)
    p, used = phrases(lang)
    y = await yukti_tools.yukti_evaluate(boat_type, h["lat"], h["lon"], lang=used)
    d = y["data"]
    req, early = d["requested"], d.get("earliest_window")
    verdict = d["verdict"]
    if verdict == "NO-GO":
        nxt = hhmm(early["depart"]) if early else None
        headline = p["verdict"]["NO-GO"].format(next_window=nxt or p.get("no_window", "—"))
    elif verdict == "CAUTION":
        headline = p["verdict"]["CAUTION"].format(back_by=hhmm(req["return_at"]))
    else:
        headline = p["verdict"]["GO"]
    fence = geo.fence_check(h["lat"], h["lon"])["data"]
    border_km = round(float(fence["imbl_km"]))
    h8 = next(e for e in req["ledger"] if e["id"] == "H8")
    card: dict[str, Any] = {
        "harbour": {"id": h["id"], "name": h["name"]},
        "boat_type": boat_type,
        "lang": used,
        "as_of": hhmm(d["as_of"]),
        "verdict": verdict,
        "headline": headline,
        "why": reasons(p, req),
        "window": (
            {"depart": hhmm(early["depart"]), "back_by": hhmm(early["return_at"]), "verdict": early["outcome"]}
            if early
            else None
        ),
        "ribbon": await asyncio.to_thread(ribbon, ctx, to_cell(h["lat"], h["lon"])),
        "spot": spot(ctx, h["lat"], h["lon"], p),
        "border": {"distance_km": border_km, "text": p["border"].format(distance_km=border_km)},
        "stale": None if h8["ok"] else p["stale"],
        "footer": footer(used),
        "answer_id": d.get("answer_id"),
        "simulation": any("SIMULATION" in n for n in y.get("notes", [])),
        "sources": sorted({i.source for i in ctx.inputs if i.available}),
        "fetched_at": y["fetched_at"],
        "phrases_version": phrases_version(),
    }
    card["speak"] = speakable(card)
    return card


async def sea_brief(harbour_id: str, boat_type: str, lang: str) -> dict[str, Any]:
    """Simple-mode sea card for a harbour (config/harbours.yaml id), a boat type (non_motorised | small_frp |
    mechanised_trawler) and a language (BCP-47, e.g. ta-IN): verdict, one-sentence reasons, the safe window,
    a 24-hour ribbon (verdict if leaving at each hour, IST), the fishing spot and the border distance in km —
    all in approved phrases. Advisory only; official INCOIS/IMD warnings always win."""
    h = harbour(harbour_id)
    start = to_cell(h["lat"], h["lon"])
    ctx, _ = await facts.gather(boat_type, start)
    parts = [
        "brief",
        harbour_id,
        boat_type,
        lang,
        norm_window30(ctx.as_of),
        config_version(),
        phrases_version(),
        layers.load().version,
        *yukti_tools._input_versions(ctx),
    ]
    return await _card(parts, ctx, harbour_id, boat_type, lang)
