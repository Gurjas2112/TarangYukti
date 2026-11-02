"""marine_forecast: hourly waves, swell, currents, SST (Open-Meteo Marine) and wind (Open-Meteo Forecast)."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import h3
from ty_common.cache import cached, fingerprint, norm_hour, to_cell
from ty_common.models import ToolResult

from .. import config, fetch, qc
from ..snapshot import SnapshotStore
from .common import finish, mode_key, now, resolve, unavailable

MAX_HOURS = 72
GRID_STEP_DEG = 0.25

# Open-Meteo field → our field, QC kind (None = no range check), decimals
MARINE_FIELDS = {
    "wave_height": ("wave_m", "wave_m", 2),
    "wave_direction": ("wave_dir_deg", None, 0),
    "wave_period": ("wave_period_s", None, 1),
    "swell_wave_height": ("swell_m", "wave_m", 2),
    "ocean_current_velocity": ("current_kmh", None, 1),
    "ocean_current_direction": ("current_dir_deg", None, 0),
    "sea_surface_temperature": ("sst_c", "sst_c", 1),
}
WIND_FIELDS = {
    "wind_speed_10m": ("wind_kmh", "wind_kmh", 1),
    "wind_gusts_10m": ("gust_kmh", "wind_kmh", 1),
    "wind_direction_10m": ("wind_dir_deg", None, 0),
}


def _params(lat: str, lon: str, fields: list[str], hours: int) -> dict[str, Any]:
    return {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(fields),
        "forecast_hours": hours,
        "timezone": "UTC",
        "wind_speed_unit": "kmh",
    }


def build_rows(
    marine: dict[str, Any], wind: dict[str, Any] | None, start: datetime | None, hours: int
) -> tuple[list[dict[str, Any]], int]:
    """Merge the two hourly blocks by time; out-of-range values become None. Returns (rows, rejected)."""
    mh, wh = marine["hourly"], (wind or {}).get("hourly", {})
    wind_by_time = {t: i for i, t in enumerate(wh.get("time", []))}
    rows, rejected = [], 0
    floor = norm_hour(start) if start else None
    for i, t in enumerate(mh["time"]):
        iso = f"{t}:00Z" if len(t) == 16 else t
        if floor and iso[:13] + "Z" < floor:
            continue
        row: dict[str, Any] = {"time": iso}
        for src, (dst, kind, nd) in MARINE_FIELDS.items():
            row[dst], bad = _clean(mh.get(src, [None] * (i + 1))[i], kind, nd)
            rejected += bad
        j = wind_by_time.get(t)
        for src, (dst, kind, nd) in WIND_FIELDS.items():
            v = wh[src][j] if j is not None and src in wh else None
            row[dst], bad = _clean(v, kind, nd)
            rejected += bad
        rows.append(row)
        if len(rows) >= hours:
            break
    return rows, rejected


def _clean(v: Any, kind: str | None, nd: int) -> tuple[float | None, int]:
    if v is None:
        return None, 0
    x = float(v)
    if kind is not None and qc.in_range(kind, x) is None:
        return None, 1
    return round(x, nd), 0


def _result(rows: list[dict[str, Any]], rejected: int, cell: str, fetched_at: datetime) -> ToolResult:
    notes = []
    if rejected:
        notes.append(f"{rejected} values outside plausible ranges were marked missing")
    no_waves = all(r["wave_m"] is None for r in rows)
    if no_waves:
        notes.append("no wave data for this cell (land or coast)")
    return ToolResult(
        data={"cell": cell, "hours": rows},
        source=f"{config.endpoint('open_meteo_marine')['name']} + {config.endpoint('open_meteo_wind')['name']}",
        source_url=config.endpoint("open_meteo_marine")["url"],
        fetched_at=fetched_at,
        valid_at=datetime.fromisoformat(rows[0]["time"]) if rows else None,
        confidence="low" if no_waves else "high",
        notes=notes,
    )


async def _online(cell: str, hours: int) -> ToolResult:
    lat, lon = h3.cell_to_latlng(cell)
    m_ep, w_ep = config.endpoint("open_meteo_marine"), config.endpoint("open_meteo_wind")
    marine = await fetch.get_json(m_ep["url"], _params(f"{lat:.4f}", f"{lon:.4f}", m_ep["hourly"], hours))
    wind = await fetch.get_json(w_ep["url"], _params(f"{lat:.4f}", f"{lon:.4f}", w_ep["hourly"], hours))
    rows, rejected = build_rows(marine, wind, None, hours)
    return _result(rows, rejected, cell, now())


def _from_snapshot(store: SnapshotStore, cell: str, hours: int) -> ToolResult:
    lat, lon = h3.cell_to_latlng(cell)
    m_doc, w_doc = store.read("marine"), store.read("wind")
    best, best_d = None, math.inf
    for i, p in enumerate(m_doc["payload"]):
        if not any(v is not None for v in p["hourly"].get("wave_height", [])):
            continue  # land point
        d = math.hypot(p["latitude"] - lat, (p["longitude"] - lon) * math.cos(math.radians(lat)))
        if d < best_d:
            best, best_d = i, d
    if best is None or best_d > GRID_STEP_DEG * 1.5:
        raise fetch.SourceUnavailable("snapshot has no sea grid point near this cell")
    marine, wind = m_doc["payload"][best], w_doc["payload"][best]
    rows, rejected = build_rows(marine, wind, now(), hours)
    if not rows:  # snapshot day already past: replay it from its first hour
        rows, rejected = build_rows(marine, wind, None, hours)
    r = _result(rows, rejected, cell, datetime.fromisoformat(m_doc["fetched_at"]))
    return r.model_copy(update={"notes": [*r.notes, f"snapshot {store.date}, nearest 0.25° grid point"]})


@cached(
    ns="tool",
    ttl=config.ttl("forecast"),
    key=lambda cell, hours: fingerprint("marine_forecast", cell, hours, norm_hour(now()), *mode_key()),
    tags=lambda cell, hours: [f"cell:{cell}", "source:open-meteo"],
)
async def _marine(cell: str, hours: int) -> dict[str, Any]:
    return await resolve(lambda: _online(cell, hours), lambda s: _from_snapshot(s, cell, hours))


async def marine_forecast(lat: float, lon: float, hours: int = 24) -> dict[str, Any]:
    """Hourly sea state for the H3 res-7 cell containing (lat, lon), starting at the current UTC hour.

    Units: wave/swell height m, wave period s, current km/h, SST °C, wind and gusts km/h at 10 m,
    directions in degrees (where it comes FROM for wind/waves). hours: 1–72. Coordinates must be inside
    the Gulf of Mannar / Palk Bay region (lat 8.0–10.5, lon 78.0–80.5).
    """
    qc.check_region(lat, lon)
    hours = max(1, min(MAX_HOURS, int(hours)))
    cell = to_cell(lat, lon)  # raw coordinates never reach the cache or the result
    try:
        return finish(await _marine(cell, hours))
    except fetch.SourceUnavailable as e:
        return unavailable("Open-Meteo Marine", config.endpoint("open_meteo_marine")["url"], str(e))


# ── snapshot capture ─────────────────────────────────────────────────────────────


def grid_points() -> list[tuple[float, float]]:
    b = qc.bbox()
    lats = _steps(b["lat_min"], b["lat_max"])
    lons = _steps(b["lon_min"], b["lon_max"])
    return [(la, lo) for la in lats for lo in lons]


def _steps(a: float, b: float) -> list[float]:
    n = round((b - a) / GRID_STEP_DEG)
    return [round(a + i * GRID_STEP_DEG, 3) for i in range(n + 1)]


async def fetch_grid() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Whole-region grid (0.25°) for the next 72 h: one multi-location request per API."""
    pts = grid_points()
    lats = ",".join(f"{p[0]}" for p in pts)
    lons = ",".join(f"{p[1]}" for p in pts)
    out: list[list[dict[str, Any]]] = []
    for ep_name in ("open_meteo_marine", "open_meteo_wind"):
        ep = config.endpoint(ep_name)
        payload = await fetch.get_json(ep["url"], _params(lats, lons, ep["hourly"], MAX_HOURS), timeout=120)
        out.append([payload] if isinstance(payload, dict) else payload)
    return out[0], out[1]


async def capture_grid(store: SnapshotStore) -> None:
    marine, wind = await fetch_grid()
    store.write("marine", marine, config.endpoint("open_meteo_marine")["url"])
    store.write("wind", wind, config.endpoint("open_meteo_wind")["url"])


# ── whole-region grid for the Yukti engine ──────────────────────────────────────


def grid_result(marine: list[dict[str, Any]], wind: list[dict[str, Any]], fetched_at: datetime) -> ToolResult:
    """Sea grid points only, each with {hour: [wave_m, wind_kmh]} (QC applied)."""
    wind_by_point = {(round(w["latitude"], 3), round(w["longitude"], 3)): w for w in wind}
    points, rejected = [], 0
    for i, m in enumerate(marine):
        if not any(v is not None for v in m["hourly"].get("wave_height", [])):
            continue  # land
        w = wind_by_point.get((round(m["latitude"], 3), round(m["longitude"], 3))) or (
            wind[i] if i < len(wind) else None
        )
        rows, bad = build_rows(m, w, None, MAX_HOURS)
        rejected += bad
        points.append(
            {
                "lat": round(m["latitude"], 4),
                "lon": round(m["longitude"], 4),
                "hours": {r["time"][:13]: [r["wave_m"], r["wind_kmh"]] for r in rows},
            }
        )
    if not points:
        raise fetch.SourceUnavailable("forecast grid has no sea points")
    notes = [f"{len(points)} sea grid points, 0.25°"]
    if rejected:
        notes.append(f"{rejected} values outside plausible ranges were marked missing")
    first = min(points[0]["hours"]) if points[0]["hours"] else None
    return ToolResult(
        data={"step_deg": GRID_STEP_DEG, "points": points},
        source=f"{config.endpoint('open_meteo_marine')['name']} + {config.endpoint('open_meteo_wind')['name']}",
        source_url=config.endpoint("open_meteo_marine")["url"],
        fetched_at=fetched_at,
        valid_at=datetime.fromisoformat(f"{first}:00:00+00:00") if first else None,
        confidence="high",
        notes=notes,
    )


@cached(
    ns="tool",
    ttl=config.ttl("forecast"),
    key=lambda: fingerprint("forecast_grid", norm_hour(now()), *mode_key()),
    tags=lambda: ["source:open-meteo", "grid"],
)
async def _grid() -> dict[str, Any]:
    async def online() -> ToolResult:
        m, w = await fetch_grid()
        return grid_result(m, w, now())

    def snap(store: SnapshotStore) -> ToolResult:
        m, w = store.read("marine"), store.read("wind")
        r = grid_result(m["payload"], w["payload"], datetime.fromisoformat(m["fetched_at"]))
        return r.model_copy(update={"notes": [*r.notes, f"snapshot {store.date}"]})

    return await resolve(online, snap)


async def forecast_grid() -> dict[str, Any]:
    """Hourly wave height (m) and wind (km/h) on the 0.25° sea grid of the whole region, next 72 h."""
    try:
        return finish(await _grid())
    except fetch.SourceUnavailable as e:
        return unavailable("Open-Meteo Marine", config.endpoint("open_meteo_marine")["url"], str(e))
