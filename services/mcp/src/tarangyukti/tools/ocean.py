"""anomaly_series and pfz_compute (spec §7 tool table) — Ocean Analytics for the Expert and analyst screens.

- anomaly_series: daily SST and its anomaly vs the 1991-2020 climatology at one OISST grid point (NOAA CoastWatch).
- pfz_compute: candidate fishing zones = thermal fronts (Sobel gradient of the SST grid) where chlorophyll is high,
  merged into polygons, plus the overlap score with the INCOIS PFZ advisory when one is available.
  Thresholds come from config/constraints.yaml `pfz_compute` (data, not code).
"""

from __future__ import annotations

import itertools
import math
from datetime import datetime
from typing import Any

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import Point, mapping
from shapely.ops import unary_union
from ty_common.cache import cached, fingerprint, norm_hour, to_cell
from ty_common.models import ToolResult

from .. import config, fetch, layers, qc
from ..snapshot import SnapshotMissing, SnapshotStore
from . import grids, warnings
from .common import finish, mode_key, now, resolve, unavailable

KM_PER_DEG_LAT = 111.32
_TO_M = Transformer.from_crs(4326, 32644, always_xy=True).transform  # same UTM zone as layers.py
_TO_DEG = Transformer.from_crs(32644, 4326, always_xy=True).transform


def transform(fn: Any, geom: Any) -> Any:
    """Apply a pyproj (x, y) transform to every coordinate of a geometry (shapely 2 API)."""
    return shapely.transform(geom, lambda xy: np.column_stack(fn(xy[:, 0], xy[:, 1])))


# ── anomaly_series ───────────────────────────────────────────────────────────────


def parse_series(payload: dict[str, Any]) -> list[dict[str, Any]]:
    t = payload["table"]
    cols = t["columnNames"]
    i_t, i_a, i_s = cols.index("time"), cols.index("anom"), cols.index("sst")
    out = []
    for row in t["rows"]:
        a, s = row[i_a], row[i_s]
        out.append(
            {
                "date": str(row[i_t])[:10],
                "sst_c": None if s is None else round(float(s), 2),
                "anom_c": None if a is None else round(float(a), 2),
            }
        )
    return out


def heatwave(series: list[dict[str, Any]]) -> dict[str, Any]:
    """Marine heatwave test from config (mean anomaly over the window ≥ anom_c on ≥ min_days valid days)."""
    p = config.constraints()["heatwave"]
    vals = [x["anom_c"] for x in series if x["anom_c"] is not None]
    if len(vals) < int(p["min_days"]):
        return {"tested": False, "reason": "not enough valid days"}
    mean = round(sum(vals) / len(vals), 2)
    days_above = sum(1 for v in vals if v >= float(p["anom_c"]))
    return {
        "tested": True,
        "mean_anom_c": mean,
        "days_above": days_above,
        "threshold_c": float(p["anom_c"]),
        "heatwave": mean >= float(p["anom_c"]),
    }


@cached(
    ns="tool",
    ttl=86400,
    key=lambda cell, lat, lon, days: fingerprint("anomaly_series", cell, days, norm_hour(now())[:10], *mode_key()),
    tags=lambda cell, lat, lon, days: ["source:sst"],
)
async def _anomaly(cell: str, lat: float, lon: float, days: int) -> dict[str, Any]:
    ep = config.endpoint("sst_anomaly")

    async def online() -> ToolResult:
        # snap to the 0.25° OISST grid centre so nearby cells share a request
        glat, glon = math.floor(lat * 4) / 4 + 0.125, math.floor(lon * 4) / 4 + 0.125
        url = f"{ep['url']}?{ep['query'].format(n=days - 1, lat=glat, lon=glon)}"
        series = parse_series(await fetch.get_json(url, timeout=90))
        if not any(x["anom_c"] is not None for x in series):
            raise fetch.SourceUnavailable("anomaly: no valid values at this point (land or masked)")
        last = series[-1]["date"]
        return ToolResult(
            data={
                "point": {"lat": glat, "lon": glon},
                "days": len(series),
                "series": series,
                "heatwave": heatwave(series),
                "climatology": "1991-2020",
            },
            source=ep["name"],
            source_url=ep["url"],
            fetched_at=now(),
            valid_at=datetime.fromisoformat(f"{last}T12:00:00+00:00"),
            confidence="high",
        )

    def snap(store: SnapshotStore) -> ToolResult:
        raise SnapshotMissing("anomaly series is not part of snapshots")

    return await resolve(online, snap)


async def anomaly_series(lat: float, lon: float, days: int = 30) -> dict[str, Any]:
    """Daily sea-surface temperature (°C) and its anomaly (°C, vs the 1991-2020 climatology) for the last `days`
    days (7–90) at the 0.25° grid point nearest (lat, lon), with a marine-heatwave test (thresholds from
    config). The point must be inside the region (lat 8.0–10.5, lon 78.0–80.5)."""
    qc.check_region(lat, lon)
    days = max(7, min(90, int(days)))
    ep = config.endpoint("sst_anomaly")
    try:
        return finish(await _anomaly(to_cell(lat, lon, 5), lat, lon, days))
    except fetch.SourceUnavailable as e:
        return unavailable(ep["name"], ep["url"], str(e))


# ── pfz_compute ──────────────────────────────────────────────────────────────────


def sst_fronts(points: list[dict[str, float]]) -> tuple[list[tuple[float, float, float]], float]:
    """Sobel gradient magnitude (°C per 10 km) on the regular SST grid. Returns [(lat, lon, grad)] and the grid
    step in degrees. Masked neighbours make a cell's gradient unknown (skipped), never interpolated."""
    lats = sorted({p["lat"] for p in points})
    lons = sorted({p["lon"] for p in points})
    if len(lats) < 3 or len(lons) < 3:
        return [], 0.25
    step = round(min(b - a for a, b in itertools.pairwise(lons)), 4)
    grid = np.full((len(lats), len(lons)), np.nan)
    ia = {v: i for i, v in enumerate(lats)}
    io = {v: i for i, v in enumerate(lons)}
    for p in points:
        grid[ia[p["lat"]], io[p["lon"]]] = p["value"]
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=float) / 8.0
    ky = kx.T
    out = []
    for i in range(1, len(lats) - 1):
        km_x = step * KM_PER_DEG_LAT * math.cos(math.radians(lats[i]))
        km_y = step * KM_PER_DEG_LAT
        for j in range(1, len(lons) - 1):
            win = grid[i - 1 : i + 2, j - 1 : j + 2]
            if np.isnan(win).any():
                continue
            gx = float((win * kx).sum()) / km_x
            gy = float((win * ky).sum()) / km_y
            out.append((lats[i], lons[j], round(math.hypot(gx, gy) * 10, 3)))
    return out, step


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat2 - lat1) * KM_PER_DEG_LAT
    dx = (lon2 - lon1) * KM_PER_DEG_LAT * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def zones(
    sst_points: list[dict[str, float]], chl_points: list[dict[str, float]], p: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[tuple[float, float, float]]]:
    fronts_all, _ = sst_fronts(sst_points)
    fronts = [f for f in fronts_all if f[2] >= float(p["front_c_per_10km"])]
    reach = float(p["front_reach_km"])
    hits = [
        c
        for c in chl_points
        if c["value"] >= float(p["chl_min_mg_m3"]) and any(_km(c["lat"], c["lon"], f[0], f[1]) <= reach for f in fronts)
    ]
    ly = layers.load()
    to_m, to_deg = _TO_M, _TO_DEG
    r_m = float(p["zone_buffer_km"]) * 500  # radius = half the disc width
    discs = [transform(to_m, Point(c["lon"], c["lat"])).buffer(r_m) for c in hits]
    merged = unary_union(discs) if discs else None
    geoms = [] if merged is None else (list(merged.geoms) if hasattr(merged, "geoms") else [merged])
    out: list[dict[str, Any]] = []
    for g in geoms:
        members = [c for c, d in zip(hits, discs, strict=True) if g.intersects(d)]
        if len(members) < int(p["min_points"]):
            continue
        inside = g.representative_point()
        if not ly.india_side.contains(inside) or ly.land_prepared.contains(inside):
            continue  # keep zones at sea on India's side of the IMBL
        c = transform(to_deg, g.centroid)
        out.append(
            {
                "id": f"Z{len(out) + 1}",
                "centroid": {"lat": round(c.y, 4), "lon": round(c.x, 4)},
                "area_km2": round(g.area / 1e6, 1),
                "points": len(members),
                "mean_chl_mg_m3": round(sum(m["value"] for m in members) / len(members), 3),
                "geometry": mapping(transform(to_deg, g).simplify(0.005)),
            }
        )
    return out, fronts


def overlap(zs: list[dict[str, Any]], incois: list[dict[str, Any]]) -> float | None:
    """Share of INCOIS PFZ points that fall inside a computed zone (None when INCOIS has no advisory)."""
    if not incois:
        return None
    from shapely.geometry import shape

    polys = [shape(z["geometry"]) for z in zs]
    inside = sum(1 for z in incois if any(pg.contains(Point(float(z["lon"]), float(z["lat"]))) for pg in polys))
    return round(inside / len(incois), 2)


@cached(
    ns="tool",
    ttl=86400,
    key=lambda: fingerprint("sst_fronts", norm_hour(now())[:10], *mode_key()),
    tags=lambda: ["source:sst"],
)
async def _front_sst() -> dict[str, Any]:
    """High-resolution SST points (MUR, 0.05° sampling) for front detection; masked cells left out."""
    ep = config.endpoint("sst_fronts")
    b = {k: float(v) for k, v in qc.bbox().items()}

    async def online() -> ToolResult:
        payload = await fetch.get_json(f"{ep['url']}?{ep['query'].format(**b)}", timeout=120)
        pts, missing, rejected, when = grids.parse("sst", payload, b)
        if not pts:
            raise fetch.SourceUnavailable("sst_fronts: no valid values")
        return ToolResult(
            data={"time": when, "points": pts, "masked": missing, "rejected": rejected},
            source=ep["name"],
            source_url=ep["url"],
            fetched_at=now(),
            valid_at=datetime.fromisoformat(when.replace("Z", "+00:00")) if when else None,
            confidence="high",
        )

    def snap(store: SnapshotStore) -> ToolResult:
        raise SnapshotMissing("high-resolution SST is not part of snapshots")

    return await resolve(online, snap)


async def pfz_compute() -> dict[str, Any]:
    """Candidate fishing zones for the whole region from the latest SST and chlorophyll: thermal fronts (Sobel
    gradient of SST, °C per 10 km) where chlorophyll-a (mg/m³) is high, merged into polygons (GeoJSON, degrees),
    each with area (km²) and mean chlorophyll. `overlap_incois` is the share (0–1) of the INCOIS PFZ points inside
    a computed zone, or null when there is no INCOIS advisory. Computed zones are guidance for analysts; the
    official advisory is INCOIS's."""
    p = config.constraints()["pfz_compute"]
    chl, pfz = await grids.chl_grid(), await warnings.pfz_incois()
    try:
        sst = await _front_sst()
    except fetch.SourceUnavailable as e:
        return unavailable("pfz_compute (TarangYukti)", "urn:tarangyukti:pfz_compute", f"SST unavailable: {e}")
    if chl["data"].get("available") is False:
        return unavailable("pfz_compute (TarangYukti)", "urn:tarangyukti:pfz_compute", "chlorophyll grid unavailable")
    zs, fronts = zones(sst["data"]["points"], chl["data"]["points"], p)
    incois = pfz["data"].get("zones", []) if pfz["data"].get("available") is not False else []
    notes = [f"SST {sst['data']['time']}", f"chlorophyll {chl['data']['time']}"]
    if chl["data"]["stats"]["masked_fraction"] > 0.5:
        notes.append(f"{int(chl['data']['stats']['masked_fraction'] * 100)}% of chlorophyll cells cloud-masked")
    if not incois:
        notes.append("no INCOIS PFZ advisory to compare with")
    return ToolResult(
        data={
            "zones": zs,
            "front_cells": len(fronts),
            "thresholds": p,
            "overlap_incois": overlap(zs, incois),
            "incois_points": len(incois),
        },
        source=f"Computed from {sst['source']} and {chl['source']}",
        source_url="urn:tarangyukti:pfz_compute",
        fetched_at=now(),
        valid_at=datetime.fromisoformat(chl["data"]["time"].replace("Z", "+00:00"))
        if chl["data"].get("time")
        else None,
        confidence="medium" if zs else "low",
        notes=notes,
    ).model_dump(mode="json")
