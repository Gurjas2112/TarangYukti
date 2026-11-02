"""Time-expanded A* on H3 resolution-7 cells (prompt §6, spec §6.3.1).

Nodes are (cell, time). Moving to a neighbour costs its distance × (1 + weather penalty) and advances the
clock by the travel time at the boat's speed, so weather is checked for the hour the boat is actually
there. Removed cells: land, beyond or within `imbl_min_km` of the IMBL (H2), the marine park (H3), and
anything outside the region. With `weather_aware`, a node whose forecast breaks the boat's wave or wind
limit (H5/H6) or that sits under a thunderstorm alert (H7) at that time is skipped. The heuristic is
straight-line km, which never overestimates the cost (cost ≥ distance), so the first path to reach the
goal is optimal.
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass
from datetime import datetime, timedelta

import h3

from .yukti.constraints import _active_at, covers
from .yukti.model import Ctx, Stop


@dataclass(frozen=True)
class Path:
    stops: tuple[Stop, ...]
    km: float
    arrive: datetime


def dist_km(a: str, b: str) -> float:
    return float(h3.great_circle_distance(h3.cell_to_latlng(a), h3.cell_to_latlng(b), unit="km"))


def fenced(ctx: Ctx, cell: str) -> bool:
    """Breaks H2 (beyond or within imbl_min_km of the IMBL) or H3 (marine park)."""
    f = ctx.fence(cell)
    return f.beyond_or_crossing or f.touches_mpa or f.imbl_min_km < float(ctx.hard("H2")["imbl_min_km"])


def removed(ctx: Ctx, cell: str, keep: set[str]) -> bool:
    """Fenced cells and land — never entered, except the start and goal themselves (a harbour cell is
    often land at this resolution)."""
    if cell in keep:
        return False
    return ctx.fence(cell).land or fenced(ctx, cell)


def weather_blocked(ctx: Ctx, cell: str, at: datetime) -> bool:
    """H5/H6 at this hour (missing forecast blocks too), or a thunderstorm alert over the cell (H7)."""
    w = ctx.weather(cell, at)
    if w is None or w.wave_m is None or w.wind_kmh is None:
        return True
    if w.wave_m > float(ctx.boat["max_wave_m"]) or w.wind_kmh > float(ctx.boat["max_wind_kmh"]):
        return True
    h7 = set(ctx.hard("H7").get("kinds", ["thunderstorm"]))
    issuers = set(ctx.hard("H1").get("issuers", ["IMD", "INCOIS"]))
    return any(
        w2.kind in h7 and w2.issuer in issuers and _active_at(w2, at) and covers(w2, cell, ctx.region_names)
        for w2 in ctx.warnings
    )


def penalty(ctx: Ctx, cell: str, at: datetime) -> float:
    w = ctx.weather(cell, at)
    if w is None or w.wave_m is None or w.wind_kmh is None:
        return 1.0
    return max(w.wave_m / float(ctx.boat["max_wave_m"]), w.wind_kmh / float(ctx.boat["max_wind_kmh"]))


def astar(ctx: Ctx, start: str, goal: str, depart: datetime, weather_aware: bool = True) -> Path | None:
    keep = {start, goal}
    if goal != start and fenced(ctx, goal):
        return None
    speed = ctx.speed_kmh
    search = ctx.params["search"]
    horizon_h = float(search["horizon_h"]) * 2  # a trip may end after the departure horizon
    budget = int(search["max_expansions"])
    tie = itertools.count()
    # (f = g + h, g, tiebreak, cell, hours since departure, path)
    open_: list[tuple[float, float, int, str, float, tuple[str, ...], tuple[float, ...]]] = [
        (dist_km(start, goal), 0.0, next(tie), start, 0.0, (start,), (0.0,))
    ]
    seen: set[tuple[str, int]] = set()
    expansions = 0
    while open_ and expansions < budget:
        _, g, _, cell, t, path, times = heapq.heappop(open_)
        if cell == goal:
            stops = tuple(Stop(c, depart + timedelta(hours=h)) for c, h in zip(path, times, strict=True))
            km = sum(dist_km(a, b) for a, b in itertools.pairwise(path))
            return Path(stops=stops, km=round(km, 2), arrive=depart + timedelta(hours=t))
        key = (cell, int(t * 6))  # 10-minute time buckets
        if key in seen:
            continue
        seen.add(key)
        expansions += 1
        for nb in h3.grid_ring(cell, 1):
            if removed(ctx, nb, keep):
                continue
            d = dist_km(cell, nb)
            t2 = t + d / speed
            if t2 > horizon_h:
                continue
            at = depart + timedelta(hours=t2)
            if weather_aware and nb != goal and weather_blocked(ctx, nb, at):
                continue
            g2 = g + d * (1 + (penalty(ctx, nb, at) if weather_aware else 0.0))
            heapq.heappush(open_, (g2 + dist_km(nb, goal), g2, next(tie), nb, t2, (*path, nb), (*times, t2)))
    return None
