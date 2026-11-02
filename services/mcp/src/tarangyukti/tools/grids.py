"""sst_grid and chl_grid: gridded sea-surface temperature and chlorophyll from NOAA CoastWatch ERDDAP."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Literal

from ty_common.cache import cached, fingerprint, norm_hour
from ty_common.models import ToolResult

from .. import config, fetch, qc
from ..snapshot import SnapshotStore
from .common import finish, mode_key, now, resolve, unavailable

Kind = Literal["sst", "chl"]
QC_KIND = {"sst": "sst_c", "chl": "chl_mg_m3"}
UNIT = {"sst": "°C", "chl": "mg/m³"}
DECIMALS = {"sst": 2, "chl": 3}
MAX_POINTS = 2000


def _url(kind: Kind, b: dict[str, float]) -> str:
    ep = config.endpoint(kind)
    return f"{ep['url']}?{ep['query'].format(**b)}"


def parse(kind: Kind, payload: dict[str, Any], b: dict[str, float]) -> tuple[list[dict[str, float]], int, int, str]:
    """ERDDAP .json table → points inside bbox. Returns (points, missing, rejected, time)."""
    t = payload["table"]
    cols = t["columnNames"]
    i_t, i_la, i_lo, i_v = cols.index("time"), cols.index("latitude"), cols.index("longitude"), len(cols) - 1
    pts, missing, rejected, when = [], 0, 0, ""
    for row in t["rows"]:
        la, lo = float(row[i_la]), float(row[i_lo])
        if not (b["lat_min"] <= la <= b["lat_max"] and b["lon_min"] <= lo <= b["lon_max"]):
            continue
        when = row[i_t]
        v = row[i_v]
        if v is None:
            missing += 1  # cloud / land mask: marked missing, never interpolated
            continue
        if qc.in_range(QC_KIND[kind], float(v)) is None:
            rejected += 1
            continue
        pts.append({"lat": round(la, 4), "lon": round(lo, 4), "value": round(float(v), DECIMALS[kind])})
    return pts, missing, rejected, when


def _result(kind: Kind, payload: dict[str, Any], b: dict[str, float], fetched_at: datetime) -> ToolResult:
    pts, missing, rejected, when = parse(kind, payload, b)
    total = len(pts) + missing + rejected
    if not pts:
        raise fetch.SourceUnavailable(f"{kind}: no valid values in this area (all masked)")
    values = [p["value"] for p in pts]
    valid_at = datetime.fromisoformat(when) if when else None
    stride = max(1, math.ceil(len(pts) / MAX_POINTS))
    notes = []
    if missing:
        notes.append(f"{missing} of {total} cells masked (cloud or land) and left missing")
    if rejected:
        notes.append(f"{rejected} values outside plausible range rejected")
    if stride > 1:
        notes.append(f"points thinned 1 in {stride} (stats use all points)")
    age = qc.age_hours(valid_at, now()) if valid_at else None
    limit = qc.freshness_limit_h(kind)
    if age is not None and age > limit:
        notes.append(f"data is {age} h old (limit {limit} h)")
    ep = config.endpoint(kind)
    return ToolResult(
        data={
            "variable": kind,
            "unit": UNIT[kind],
            "bbox": b,
            "time": when,
            "age_hours": age,
            "stats": {
                "min": min(values),
                "max": max(values),
                "mean": round(sum(values) / len(values), DECIMALS[kind]),
                "valid_points": len(pts),
                "masked_fraction": round(missing / total, 3) if total else 0.0,
            },
            "points": pts[::stride],
        },
        source=ep["name"],
        source_url=ep["url"],
        fetched_at=fetched_at,
        valid_at=valid_at,
        confidence="high" if (age is not None and age <= limit and (missing + rejected) / total < 0.5) else "medium",
        notes=notes,
    )


def _bbox(
    lat_min: float | None, lat_max: float | None, lon_min: float | None, lon_max: float | None
) -> dict[str, float]:
    region = qc.bbox()
    b = {
        "lat_min": region["lat_min"] if lat_min is None else lat_min,
        "lat_max": region["lat_max"] if lat_max is None else lat_max,
        "lon_min": region["lon_min"] if lon_min is None else lon_min,
        "lon_max": region["lon_max"] if lon_max is None else lon_max,
    }
    qc.check_region(b["lat_min"], b["lon_min"])
    qc.check_region(b["lat_max"], b["lon_max"])
    if b["lat_min"] >= b["lat_max"] or b["lon_min"] >= b["lon_max"]:
        raise qc.OutOfRegion("bbox minimum must be below its maximum")
    return {k: round(v, 2) for k, v in b.items()}


def _make(kind: Kind) -> Any:
    @cached(
        ns="tool",
        ttl=config.ttl(kind),
        key=lambda b: fingerprint(f"{kind}_grid", b, norm_hour(now())[:10], *mode_key()),
        tags=lambda b: [f"source:{kind}"],
    )
    async def run(b: dict[str, float]) -> dict[str, Any]:
        async def online() -> ToolResult:
            payload = await fetch.get_json(_url(kind, b), timeout=90)
            return _result(kind, payload, b, now())

        def snap(store: SnapshotStore) -> ToolResult:
            doc = store.read(kind)
            r = _result(kind, doc["payload"], b, datetime.fromisoformat(doc["fetched_at"]))
            return r.model_copy(update={"notes": [*r.notes, f"snapshot {store.date}"]})

        return await resolve(online, snap)

    return run


_sst, _chl = _make("sst"), _make("chl")


async def sst_grid(
    lat_min: float | None = None,
    lat_max: float | None = None,
    lon_min: float | None = None,
    lon_max: float | None = None,
) -> dict[str, Any]:
    """Latest daily sea-surface temperature (°C) on a 0.25° grid (NOAA OISST v2.1 NRT).

    Bounding box defaults to the whole region (lat 8.0–10.5, lon 78.0–80.5) and must stay inside it.
    Returns stats (min/max/mean), the data time, its age in hours and up to 2,000 points.
    """
    b = _bbox(lat_min, lat_max, lon_min, lon_max)
    try:
        return finish(await _sst(b))
    except fetch.SourceUnavailable as e:
        return unavailable(config.endpoint("sst")["name"], config.endpoint("sst")["url"], str(e))


async def chl_grid(
    lat_min: float | None = None,
    lat_max: float | None = None,
    lon_min: float | None = None,
    lon_max: float | None = None,
) -> dict[str, Any]:
    """Latest daily chlorophyll-a (mg/m³) on a ~4 km grid (NOAA-20 VIIRS NRT).

    Cloud-covered cells are left missing (masked_fraction says how many). Bounding box defaults to the
    whole region (lat 8.0–10.5, lon 78.0–80.5) and must stay inside it.
    """
    b = _bbox(lat_min, lat_max, lon_min, lon_max)
    try:
        return finish(await _chl(b))
    except fetch.SourceUnavailable as e:
        return unavailable(config.endpoint("chl")["name"], config.endpoint("chl")["url"], str(e))


async def capture(store: SnapshotStore, kind: Kind) -> None:
    b = {k: float(v) for k, v in qc.bbox().items()}
    payload = await fetch.get_json(_url(kind, b), timeout=180)
    store.write(kind, payload, config.endpoint(kind)["url"])
