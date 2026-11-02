"""MCP tools: yukti_evaluate (verdict + earliest safe window + ledger) and route_safest."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from ty_common.cache import cached, config_version, fingerprint, norm_window30, to_cell
from ty_common.models import ToolResult

from .. import layers, ledger, qc, route
from ..yukti import engine, facts
from ..yukti.model import Ctx, Evaluation
from .common import finish

SOURCE = "Yukti constraint engine (TarangYukti)"
URL = "urn:tarangyukti:yukti"


def _eval_dict(ev: Evaluation) -> dict[str, Any]:
    c = ev.candidate
    return {
        "outcome": ev.outcome,
        "feasible": ev.feasible,
        "failed_hard": ev.failed_hard(),
        "risk": ev.risk,
        "score": ev.score,
        "depart": c.depart.isoformat(),
        "return_at": c.return_at.isoformat(),
        "route_km": c.route_km,
        "route_cells": list(c.cells) if c.goal_cell else [],
        "local_area_cells": len(c.cells) if c.goal_cell is None else 0,
        "notes": list(c.notes),
        "ledger": [e.as_dict() for e in ev.ledger],
    }


def _input_versions(ctx: Ctx) -> list[str]:
    return [f"{i.name}@{i.fetched_at.isoformat()}:{i.available}" for i in ctx.inputs] + sorted(
        f"{w.id}:{w.valid_to.isoformat()}" for w in ctx.warnings
    )


def _parse_time(depart_at: str | None) -> datetime | None:
    if not depart_at:
        return None
    t = datetime.fromisoformat(depart_at)
    if t.tzinfo is None:
        raise ValueError("depart_at needs a timezone, e.g. 2026-11-04T04:00:00+05:30")
    return t


@cached(
    ns="yukti",
    ttl=900,
    key=lambda parts, ctx, start, goal, depart: fingerprint(*parts),
    tags=lambda parts, ctx, start, goal, depart: [f"cell:{start}"],
)
async def _plan(parts: list[str], ctx: Ctx, start: str, goal: str | None, depart: datetime | None) -> dict[str, Any]:
    plan = await asyncio.to_thread(engine.plan_trip, ctx, start, goal, depart)
    return {
        "requested": _eval_dict(plan.requested),
        "earliest_window": _eval_dict(plan.earliest) if plan.earliest else None,
        "recommended": _eval_dict(plan.best) if plan.best else None,
        "checked_departures": plan.checked,
    }


async def yukti_evaluate(
    boat_type: str,
    lat: float,
    lon: float,
    goal_lat: float | None = None,
    goal_lon: float | None = None,
    depart_at: str | None = None,
    lang: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Decide GO / CAUTION / NO-GO for a fishing trip with the deterministic constraint engine (H1–H8 hard,
    S1–S5 soft), and find the earliest departure that passes every hard constraint in the next 24 h
    (30-minute steps).

    boat_type: non_motorised | small_frp | mechanised_trawler. (lat, lon): harbour or current position.
    (goal_lat, goal_lon): fishing spot, or omit for a trip in the waters near the harbour (within 10 km).
    depart_at: ISO time with timezone (default: now). All points must be inside the region (lat 8.0–10.5,
    lon 78.0–80.5). Returns `requested` (that departure), `earliest_window` and `recommended` (or null when
    no departure passes), each with the Constraint Ledger; `answer_id` when the ledger was stored.
    The verdict is advisory only — official INCOIS/IMD warnings always win.
    """
    qc.check_region(lat, lon)
    start = to_cell(lat, lon)
    goal = None
    if goal_lat is not None and goal_lon is not None:
        qc.check_region(goal_lat, goal_lon)
        goal = to_cell(goal_lat, goal_lon)
    depart = _parse_time(depart_at)
    ctx, raw = await facts.gather(boat_type, start)
    parts = [
        "yukti",
        start,
        goal or "",
        boat_type,
        norm_window30(depart or ctx.as_of),
        config_version(),
        layers.load().version,
        *_input_versions(ctx),
    ]
    plan = await _plan(parts, ctx, start, goal, depart)

    # the ledger is written per answer (never cached): re-evaluate the requested departure for its entries
    answer_id = None
    requested_at = datetime.fromisoformat(plan["requested"]["depart"])
    req_eval = await asyncio.to_thread(lambda: engine.evaluate(ctx, engine.candidate(ctx, start, goal, requested_at)))
    params = ledger.build_params(
        ctx, req_eval, ledger.new_answer_id(), thread_id, lang, config_version(), layers.load().version[:12]
    )
    if await ledger.write(params):
        answer_id = params["answer"]["id"]

    h8 = next(e for e in plan["requested"]["ledger"] if e["id"] == "H8")
    notes = [f"as of {ctx.as_of.isoformat()}"]
    if any(r["cache"] == "snapshot" for r in raw):
        notes.append("based on snapshot data")
    if any(w.simulation for w in ctx.warnings):
        notes.append("SIMULATION: a simulated warning is part of the inputs")
    return finish(
        ToolResult(
            data={
                "verdict": plan["requested"]["outcome"],
                "boat_type": boat_type,
                "as_of": ctx.as_of.isoformat(),
                **plan,
                "answer_id": answer_id,
            },
            source=SOURCE,
            source_url=URL,
            fetched_at=ctx.as_of,
            valid_at=datetime.fromisoformat(plan["requested"]["depart"]),
            confidence="high" if h8["ok"] else "low",
            notes=notes,
        ).model_dump(mode="json")
    )


@cached(
    ns="route",
    ttl=900,
    key=lambda parts, ctx, start, goal, depart: fingerprint(*parts),
    tags=lambda parts, ctx, start, goal, depart: [f"cell:{start}", f"cell:{goal}"],
)
async def _route(parts: list[str], ctx: Ctx, start: str, goal: str, depart: datetime) -> dict[str, Any]:
    path = await asyncio.to_thread(route.astar, ctx, start, goal, depart)
    if path is None:
        return {"found": False, "reason": "no route avoids the border buffer, the marine park, land and bad weather"}
    return {
        "found": True,
        "km": path.km,
        "depart": depart.isoformat(),
        "arrive": path.arrive.isoformat(),
        "cells": [s.cell for s in path.stops],
        "times": [s.at.isoformat() for s in path.stops],
    }


async def route_safest(
    boat_type: str, lat: float, lon: float, goal_lat: float, goal_lon: float, depart_at: str | None = None
) -> dict[str, Any]:
    """Safest sea route between two points for a boat type, leaving at depart_at (ISO with timezone;
    default now): time-expanded A* on H3 cells (~5 km²) that never enters land, the marine park or cells
    within 5 km of the border line, and skips cells whose forecast at the hour the boat is there breaks
    the boat's wave/wind limits or has a thunderstorm alert. Returns cells, times and length in km.
    """
    qc.check_region(lat, lon)
    qc.check_region(goal_lat, goal_lon)
    start, goal = to_cell(lat, lon), to_cell(goal_lat, goal_lon)
    ctx, _ = await facts.gather(boat_type, start)
    depart = _parse_time(depart_at) or ctx.as_of
    parts = [
        "route",
        start,
        goal,
        boat_type,
        norm_window30(depart),
        config_version(),
        layers.load().version,
        *_input_versions(ctx),
    ]
    data = await _route(parts, ctx, start, goal, depart)
    return finish(
        ToolResult(
            data=data,
            source=SOURCE,
            source_url=URL,
            fetched_at=ctx.as_of,
            valid_at=depart,
            confidence="high" if data["found"] else "medium",
        ).model_dump(mode="json")
    )
