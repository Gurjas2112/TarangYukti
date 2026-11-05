"""Gather the facts for one evaluation through the data tools and build a Ctx (the only I/O in Yukti).

`as_of` is "now" online. With DATA_MODE=snapshot it is the forecast's capture time, so a demo replays
the snapshot day as it was and H8 measures freshness against that moment.
"""

from __future__ import annotations

import asyncio
import dataclasses
import functools
import math
from datetime import UTC, date, datetime, timedelta
from typing import Any

import h3
from ty_common import capture
from ty_common.settings import get_settings

from .. import config, layers
from ..tools import marine, warnings
from ..tools.alert_model import Warning_
from ..tools.common import now
from .model import Ctx, InputInfo, Weather
from .sun import sunset_utc

WARNING_INPUTS = (
    ("warnings_imd", warnings.imd_warnings),
    ("warnings_incois", warnings.incois_alerts),
    ("warnings_sdma", warnings.sdma_alerts),
)


def _info(name: str, kind: str, r: dict[str, Any]) -> InputInfo:
    available = not (isinstance(r["data"], dict) and r["data"].get("available") is False)
    return InputInfo(
        name=name,
        kind=kind,
        source=r["source"],
        source_url=r["source_url"],
        fetched_at=datetime.fromisoformat(r["fetched_at"]),
        available=available,
        cache=r["cache"],
    )


def weather_lookup(points: list[dict[str, Any]]) -> Any:
    """(cell, time) → Weather from the nearest sea grid point's forecast for that UTC hour."""

    @functools.lru_cache(maxsize=50_000)
    def nearest(cell: str) -> int | None:
        lat, lon = h3.cell_to_latlng(cell)
        best, best_d = None, math.inf
        for i, p in enumerate(points):
            d = math.hypot(p["lat"] - lat, (p["lon"] - lon) * math.cos(math.radians(lat)))
            if d < best_d:
                best, best_d = i, d
        return best if best_d <= marine.GRID_STEP_DEG * 1.5 else None

    def weather(cell: str, at: datetime) -> Weather | None:
        i = nearest(cell)
        if i is None:
            return None
        row = points[i]["hours"].get(at.astimezone(UTC).strftime("%Y-%m-%dT%H"))
        return None if row is None else Weather(wave_m=row[0], wind_kmh=row[1])

    return weather


async def gather(boat_type: str, start_cell: str) -> tuple[Ctx, list[dict[str, Any]]]:
    """Ctx for one evaluation plus the raw tool results (for provenance)."""
    boats = config.load("boats.yaml")
    if boat_type not in boats or boat_type == "version":
        raise ValueError(f"unknown boat type {boat_type!r}; one of {[b for b in boats if b != 'version']}")

    grid, *alerts = await asyncio.gather(
        marine.forecast_grid(), *(fn() for _, fn in WARNING_INPUTS), return_exceptions=False
    )
    pfz = await warnings.pfz_incois()
    inputs = [_info("forecast", "waves", grid)]
    inputs += [_info(name, "warnings", r) for (name, _), r in zip(WARNING_INPUTS, alerts, strict=True)]
    pfz_info = _info("pfz", "pfz", pfz)
    if pfz_info.available:
        inputs.append(pfz_info)

    ws: list[Warning_] = []
    for r in alerts:
        d = r["data"]
        if isinstance(d, dict):
            ws += [Warning_.model_validate(w) for w in [*d.get("active", []), *d.get("upcoming", [])]]

    points = grid["data"].get("points", []) if isinstance(grid["data"], dict) else []
    if capture.active("no-safe-window"):  # walkthrough: every hour above every boat's wave limit
        points = [p | {"hours": {t: [9.9, *row[1:]] for t, row in p["hours"].items()}} for p in points]
    snapshot_mode = get_settings().data_mode == "snapshot"
    as_of = inputs[0].fetched_at if snapshot_mode and inputs[0].available else now()
    if capture.active("stale-data"):  # walkthrough: warnings older than the H8 limit → never GO
        inputs = [
            dataclasses.replace(i, fetched_at=as_of - timedelta(hours=72)) if i.kind == "warnings" else i
            for i in inputs
        ]
    lat0, lon0 = h3.cell_to_latlng(start_cell)

    def sunset(day: date) -> datetime:
        return sunset_utc(day, lat0, lon0)

    pfz_points = (
        [(float(z["lat"]), float(z["lon"])) for z in pfz["data"].get("zones", [])] if pfz_info.available else []
    )
    ctx = Ctx(
        as_of=as_of,
        boat_type=boat_type,
        boat=boats[boat_type],
        params=config.constraints(),
        weather=weather_lookup(points),
        fence=layers.fence_flags,
        warnings=ws,
        inputs=inputs,
        sunset=sunset,
        pfz_points=pfz_points,
        region_names=tuple(config.qc()["region"]["alert_area_names"]),
    )
    return ctx, [grid, *alerts, pfz]
