"""The Yukti loop (spec §6.1.2): propose candidates (departure windows × route) → check hard constraints →
repair (shift the window by 30 min, re-route around removed cells) → score soft constraints → best
feasible option + Constraint Ledger.

Outcome mapping: any hard failure → NO-GO; all hard pass and risk ≥ caution_at → CAUTION; else GO
("GO — no constraint violated, advisory only").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import h3

from .. import route
from .constraints import REGISTRY, risk_of
from .model import Candidate, Ctx, Evaluation, LedgerEntry, Outcome, Stop

ORDER = ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "S1", "S2", "S3", "S4", "S5"]
RANK: dict[Outcome, int] = {"GO": 0, "CAUTION": 1, "NO-GO": 2}


def evaluate(ctx: Ctx, cand: Candidate, kind: str = "trip") -> Evaluation:
    ledger: list[LedgerEntry] = []
    for cid in ORDER:
        c = REGISTRY[cid]
        if kind not in c.applies_to:
            continue
        params = ctx.params["hard" if c.kind == "hard" else "soft"][cid]
        v = c.fn(ctx, cand, params)
        ledger.append(
            LedgerEntry(
                cid, c.kind, str(params.get("name", cid)), v.ok, v.value, v.unit, v.evidence, v.detail, v.at, v.unknown
            )
        )
    if not cand.route_found:  # H2/H3 decide reachability: one H2 entry says so
        ledger = [
            LedgerEntry(
                "H2",
                "hard",
                e.name,
                False,
                "no route",
                None,
                ("layer:imbl", "layer:mpa_gom", "layer:land"),
                "the spot cannot be reached without crossing the border buffer, the marine park or land",
                None,
                False,
            )
            if e.id == "H2"
            else e
            for e in ledger
        ]
    feasible = all(e.ok for e in ledger if e.kind == "hard")
    risk = risk_of(ctx, cand)
    caution_at = float(ctx.soft("S3")["caution_at"])
    outcome: Outcome = "NO-GO" if not feasible else ("CAUTION" if risk is None or risk >= caution_at else "GO")
    return Evaluation(
        cand, outcome, feasible, None if risk is None else round(risk, 2), _score(ctx, ledger, risk), tuple(ledger)
    )


def _score(ctx: Ctx, ledger: list[LedgerEntry], risk: float | None) -> float:
    s = 1.0 - (risk if risk is not None else 1.0)
    for e in ledger:
        if e.kind == "soft" and e.id in ("S1", "S2", "S4", "S5") and e.ok and not e.unknown:
            s += float(ctx.soft(e.id).get("weight", 0.0))
    return round(s, 3)


# ── candidates ───────────────────────────────────────────────────────────────────


def local_area(ctx: Ctx, start: str) -> list[str]:
    """Sea cells within local_radius_km of the harbour that a boat may use (removed cells dropped)."""
    edge_km = h3.average_hexagon_edge_length(h3.get_resolution(start), unit="km")
    k = max(1, round(float(ctx.params["search"]["local_radius_km"]) / (edge_km * 1.5)))
    return [c for c in h3.grid_disk(start, k) if c == start or not route.removed(ctx, c, {start})]


def hourly(t0: datetime, t1: datetime) -> list[datetime]:
    out, t = [], t0
    while t <= t1:
        out.append(t)
        t += timedelta(hours=1)
    if out[-1] != t1:
        out.append(t1)
    return out


def local_candidate(ctx: Ctx, start: str, depart: datetime) -> Candidate:
    ret = depart + timedelta(hours=float(ctx.boat["local_trip_h"]))
    cells = local_area(ctx, start)
    stops = tuple(Stop(c, at) for at in hourly(depart, ret) for c in cells)
    return Candidate(
        depart=depart,
        return_at=ret,
        timeline=stops,
        start_cell=start,
        goal_cell=None,
        route_km=float(ctx.params["search"]["local_radius_km"]) * 2,
        notes=(f"local trip: {len(cells)} sea cells within the harbour radius",),
    )


def route_candidate(ctx: Ctx, start: str, goal: str, depart: datetime) -> Candidate:
    """Out to the goal, fish there for fish_h, come back. Weather-aware route first; if none exists, the
    fence-only route (so the ledger can say which weather constraint fails); if even that fails, the
    direct start → goal pair with route_found=False."""
    fish_h = float(ctx.boat["fish_h"])
    out = route.astar(ctx, start, goal, depart) or route.astar(ctx, start, goal, depart, weather_aware=False)
    if out is None:
        return Candidate(
            depart=depart,
            return_at=depart,
            timeline=(Stop(start, depart), Stop(goal, depart)),
            start_cell=start,
            goal_cell=goal,
            route_found=False,
        )
    leave = out.arrive + timedelta(hours=fish_h)
    back = route.astar(ctx, goal, start, leave) or route.astar(ctx, goal, start, leave, weather_aware=False)
    if back is None:
        return Candidate(
            depart=depart,
            return_at=leave,
            timeline=out.stops,
            start_cell=start,
            goal_cell=goal,
            route_km=out.km,
            route_found=False,
        )
    fishing = tuple(Stop(goal, at) for at in hourly(out.arrive, leave)[1:])
    return Candidate(
        depart=depart,
        return_at=back.arrive,
        timeline=out.stops + fishing + back.stops[1:],
        start_cell=start,
        goal_cell=goal,
        route_km=round(out.km + back.km, 2),
    )


def candidate(ctx: Ctx, start: str, goal: str | None, depart: datetime) -> Candidate:
    return local_candidate(ctx, start, depart) if goal is None else route_candidate(ctx, start, goal, depart)


# ── search ───────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TripPlan:
    requested: Evaluation
    earliest: Evaluation | None  # first feasible departure (the "earliest safe window")
    best: Evaluation | None  # best-scoring feasible departure (the recommendation)
    checked: int


def departures(ctx: Ctx, after: datetime) -> list[datetime]:
    step = int(ctx.params["search"]["depart_step_min"])
    horizon = float(ctx.params["search"]["horizon_h"])
    first = after.replace(second=0, microsecond=0)
    if first.minute % step:
        first += timedelta(minutes=step - first.minute % step)
    n = int(horizon * 60 / step)
    return [first + timedelta(minutes=step * i) for i in range(n + 1)]


def plan_trip(ctx: Ctx, start: str, goal: str | None, depart: datetime | None = None) -> TripPlan:
    times = departures(ctx, depart or ctx.as_of)
    evals = [evaluate(ctx, candidate(ctx, start, goal, t)) for t in times]
    feasible = [e for e in evals if e.feasible]
    best = max(feasible, key=lambda e: (e.score, -e.candidate.depart.timestamp())) if feasible else None
    return TripPlan(requested=evals[0], earliest=feasible[0] if feasible else None, best=best, checked=len(evals))
