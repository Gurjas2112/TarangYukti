"""The constraint catalogue (prompt §6, spec Table 6-1). Thresholds come from config/constraints.yaml and
config/boats.yaml via the context; nothing numeric is decided here except the rule shapes.

Each constraint is `(ctx, candidate, params) -> Verdict`. Hard constraints with missing data return
ok=False, unknown=True — "unknown" is never GO.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import h3
from shapely.geometry import Polygon, shape
from shapely.prepared import prep

from ..tools.alert_model import Warning_
from .model import Candidate, Ctx, Verdict

IST = timezone(timedelta(hours=5, minutes=30))
Fn = Callable[[Ctx, Candidate, dict[str, object]], Verdict]


@dataclass(frozen=True)
class Constraint:
    id: str
    kind: Literal["hard", "soft"]
    applies_to: tuple[str, ...]
    fn: Fn


REGISTRY: dict[str, Constraint] = {}


def constraint(cid: str, kind: Literal["hard", "soft"], applies_to: tuple[str, ...]) -> Callable[[Fn], Fn]:
    def deco(fn: Fn) -> Fn:
        REGISTRY[cid] = Constraint(cid, kind, applies_to, fn)
        return fn

    return deco


# ── helpers ─────────────────────────────────────────────────────────────────────


@functools.lru_cache(maxsize=20_000)
def _cell_poly(cell: str) -> Polygon:
    return Polygon([(lon, lat) for lat, lon in h3.cell_to_boundary(cell)])


@functools.lru_cache(maxsize=512)
def _prepared_area(area_json: str) -> object:
    import json

    return prep(shape(json.loads(area_json)))


def covers(w: Warning_, cell: str, region_names: tuple[str, ...]) -> bool:
    """Does the alert cover this cell? Without a polygon, an alert naming a region district or sea is
    treated as covering the whole region (conservative)."""
    if w.area is not None:
        import json

        return bool(_prepared_area(json.dumps(w.area, sort_keys=True)).intersects(_cell_poly(cell)))  # type: ignore[attr-defined]
    text = f"{w.area_desc or ''} {' '.join(w.districts + w.sectors)}".casefold()
    return any(n.casefold() in text for n in region_names)


def _active_at(w: Warning_, at: datetime) -> bool:
    return w.valid_from <= at <= w.valid_to


def _alerts_hit(
    ctx: Ctx, cand: Candidate, issuers: set[str], kinds: set[str] | None, exclude: set[str]
) -> list[tuple[Warning_, datetime]]:
    hits: list[tuple[Warning_, datetime]] = []
    for w in ctx.warnings:
        if w.issuer not in issuers or (kinds is not None and w.kind not in kinds) or w.kind in exclude:
            continue
        for s in cand.timeline:
            if _active_at(w, s.at) and covers(w, s.cell, ctx.region_names):
                hits.append((w, s.at))
                break
    return hits


def _transit_cells(cand: Candidate) -> list[str]:
    """Cells outside the harbour: H2/H3 never fail on the harbour the boat leaves from."""
    return [c for c in cand.cells if c != cand.start_cell]


# ── hard constraints ───────────────────────────────────────────────────────────


@constraint("H1", "hard", ("trip", "route"))
def official_warning(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    issuers = set(p.get("issuers", ["IMD", "INCOIS"]))  # type: ignore[call-overload]
    h7_kinds = set(ctx.hard("H7").get("kinds", ["thunderstorm"]))
    hits = _alerts_hit(ctx, cand, issuers, None, h7_kinds)
    if not hits:
        return Verdict(ok=True, evidence=_warning_inputs(ctx))
    w, at = hits[0]
    return Verdict(
        ok=False,
        value=w.title,
        evidence=tuple(h[0].id for h in hits),
        detail=f"{w.issuer} {w.event or w.kind} until {w.valid_to.isoformat()}"
        + (" (SIMULATION)" if w.simulation else ""),
        at=at,
    )


def _warning_inputs(ctx: Ctx) -> tuple[str, ...]:
    return tuple(i.name for i in ctx.inputs if i.name.startswith("warnings"))


@constraint("H2", "hard", ("trip", "route"))
def imbl_buffer(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    cells = _transit_cells(cand)
    if not cells:
        return Verdict(ok=True, evidence=("layer:imbl",))
    flags = [ctx.fence(c) for c in cells]
    worst = min(flags, key=lambda f: f.imbl_min_km)
    beyond = any(f.beyond_or_crossing for f in flags)
    limit = float(p["imbl_min_km"])  # type: ignore[arg-type]
    return Verdict(
        ok=not beyond and worst.imbl_min_km >= limit,
        value=0.0 if beyond else round(worst.imbl_min_km, 1),
        unit="km",
        evidence=("layer:imbl",),
        detail="route crosses the border line" if beyond else f"closest approach in cell {worst.cell}",
    )


@constraint("H3", "hard", ("trip", "route", "zone"))
def marine_park(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    inside = [c for c in _transit_cells(cand) if ctx.fence(c).touches_mpa]
    return Verdict(
        ok=not inside,
        value=len(inside),
        unit="cells",
        evidence=("layer:mpa_gom",),
        detail="route touches the Gulf of Mannar marine park" if inside else "",
    )


@constraint("H4", "hard", ("trip", "zone"))
def fishing_ban(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    if ctx.boat_type in p.get("exempt", []):  # type: ignore[operator]
        return Verdict(ok=True, value="exempt", evidence=("config:constraints",))
    coast = str(p.get("coast", "east"))
    window: list[str] = p[coast]  # type: ignore[assignment]
    start, end = str(window[0]), str(window[1])
    md = cand.depart.strftime("%m-%d")
    in_ban = start <= md <= end
    return Verdict(
        ok=not in_ban,
        value=f"{start} to {end}",
        evidence=("config:constraints",),
        detail=f"annual {coast}-coast fishing ban for mechanised boats" if in_ban else "",
        at=cand.depart,
    )


def _limit_check(ctx: Ctx, cand: Candidate, attr: str, limit: float, unit: str, what: str) -> Verdict:
    worst: tuple[float, datetime] | None = None
    missing: datetime | None = None
    first_bad: datetime | None = None
    for s in cand.timeline:
        w = ctx.weather(s.cell, s.at)
        v = getattr(w, attr) if w is not None else None
        if v is None:
            missing = missing or s.at
            continue
        if worst is None or v > worst[0]:
            worst = (v, s.at)
        if v > limit and first_bad is None:
            first_bad = s.at
    if missing is not None:
        return Verdict(
            ok=False,
            value="unknown",
            unit=unit,
            evidence=("forecast",),
            detail=f"no {what} forecast",
            at=missing,
            unknown=True,
        )
    assert worst is not None
    return Verdict(
        ok=first_bad is None,
        value=round(worst[0], 2),
        unit=unit,
        evidence=("forecast",),
        detail=f"{what} above the boat's limit of {limit} {unit}" if first_bad else "",
        at=first_bad or worst[1],
    )


@constraint("H5", "hard", ("trip", "route"))
def wave_limit(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    return _limit_check(ctx, cand, "wave_m", float(ctx.boat["max_wave_m"]), "m", "wave height")


@constraint("H6", "hard", ("trip", "route"))
def wind_limit(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    return _limit_check(ctx, cand, "wind_kmh", float(ctx.boat["max_wind_kmh"]), "km/h", "wind")


@constraint("H7", "hard", ("trip", "route"))
def thunderstorm(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    issuers = set(ctx.hard("H1").get("issuers", ["IMD", "INCOIS"]))
    hits = _alerts_hit(ctx, cand, issuers, set(p.get("kinds", ["thunderstorm"])), set())  # type: ignore[call-overload]
    if not hits:
        return Verdict(ok=True, evidence=_warning_inputs(ctx))
    w, at = hits[0]
    return Verdict(
        ok=False,
        value=w.title,
        evidence=tuple(h[0].id for h in hits),
        detail=f"{w.issuer} {w.event or w.kind} until {w.valid_to.isoformat()}",
        at=at,
    )


@constraint("H8", "hard", ("trip", "route", "zone"))
def freshness(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    limits: dict[str, float] = p["max_age_h"]  # type: ignore[assignment]
    stale = []
    for i in ctx.inputs:
        limit = limits.get(i.kind)
        if limit is None:
            continue
        age_h = (ctx.as_of - i.fetched_at).total_seconds() / 3600.0
        if not i.available:
            stale.append(f"{i.name} unavailable")
        elif age_h > limit:
            stale.append(f"{i.name} {age_h:.1f} h old (limit {limit} h)")
    required = {"forecast", "warnings_imd", "warnings_incois"}
    missing = required - {i.name for i in ctx.inputs}
    stale += [f"{m} missing" for m in sorted(missing)]
    return Verdict(
        ok=not stale,
        value=len(stale),
        unit="stale inputs",
        evidence=tuple(i.name for i in ctx.inputs),
        detail="; ".join(stale),
        unknown=bool(stale),
    )


# ── soft constraints ───────────────────────────────────────────────────────────


@constraint("S1", "soft", ("trip", "zone"))
def pfz_score(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    if not ctx.pfz_points:
        return Verdict(ok=True, value=None, detail="not tested: no PFZ advisory available", unknown=True)
    target = cand.goal_cell or cand.start_cell
    lat, lon = h3.cell_to_latlng(target)
    km = min(h3.great_circle_distance((lat, lon), pt, unit="km") for pt in ctx.pfz_points)
    near = float(p.get("near_km", 10))  # type: ignore[arg-type]
    return Verdict(ok=km <= near, value=round(km, 1), unit="km", evidence=("pfz",), detail="nearest INCOIS PFZ")


@constraint("S2", "soft", ("trip", "route"))
def fuel_margin(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    allowed = float(ctx.boat["range_km"]) * (1 - float(p["margin"]))  # type: ignore[arg-type]
    return Verdict(
        ok=cand.route_km <= allowed,
        value=round(cand.route_km, 1),
        unit="km",
        evidence=("config:boats",),
        detail="" if cand.route_km <= allowed else f"round trip longer than {allowed:.0f} km (range less margin)",
    )


def risk_of(ctx: Ctx, cand: Candidate) -> float | None:
    """risk = max over the trip of max(wave / boat max wave, wind / boat max wind)."""
    hmax, umax = float(ctx.boat["max_wave_m"]), float(ctx.boat["max_wind_kmh"])
    r: float | None = None
    for s in cand.timeline:
        w = ctx.weather(s.cell, s.at)
        if w is None:
            continue
        parts = [
            x
            for x in (
                (w.wave_m or 0) / hmax if w.wave_m is not None else None,
                (w.wind_kmh or 0) / umax if w.wind_kmh is not None else None,
            )
            if x is not None
        ]
        if parts:
            r = max(r or 0.0, *parts)
    return r


@constraint("S3", "soft", ("trip", "route"))
def risk_margin(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    r = risk_of(ctx, cand)
    if r is None:
        return Verdict(ok=False, value=None, detail="no forecast", unknown=True)
    caution = float(p["caution_at"])  # type: ignore[arg-type]
    return Verdict(ok=r < caution, value=round(r, 2), unit="ratio", evidence=("forecast", "config:boats"))


@constraint("S4", "soft", ("trip",))
def back_before_sunset(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    if ctx.boat_type not in p.get("applies", []) or ctx.sunset is None:  # type: ignore[operator]
        return Verdict(ok=True, value="not applicable")
    sunset = ctx.sunset(cand.return_at.astimezone(IST).date())  # the local calendar day
    ok = cand.return_at <= sunset
    return Verdict(
        ok=ok,
        value=sunset.isoformat(),
        unit="sunset",
        evidence=("computed:sun",),
        detail="" if ok else "back after sunset",
        at=cand.return_at,
    )


@constraint("S5", "soft", ("trip", "route"))
def sources_agree(ctx: Ctx, cand: Candidate, p: dict[str, object]) -> Verdict:
    # TODO(tarangyukti): compare with INCOIS OSF waves once a second wave source is available.
    return Verdict(ok=True, value=None, detail="not tested: one wave forecast source", unknown=True)
