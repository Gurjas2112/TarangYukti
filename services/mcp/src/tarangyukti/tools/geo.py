"""fence_check, geo_distance and the per-cell fence flags used by route search.

fence_check and geo_distance take raw coordinates (a boat's position), so their results are never cached
(prompt §7a: no coordinates in Redis). cell_fence works on H3 cells and is cached in namespace `layer`.
"""

from __future__ import annotations

from typing import Any

import h3
from pyproj import Geod
from ty_common.cache import cached, fingerprint
from ty_common.models import ToolResult

from .. import config, layers, qc
from .common import now

_GEOD = Geod(ellps="WGS84")
COMPASS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]


def _rings() -> dict[str, float]:
    r: dict[str, float] = config.constraints()["hard"]["H2"]["alert_rings_km"]
    return r


def ring_for(distance_km: float, beyond: bool) -> str:
    """beyond | alarm (≤ 2 km) | warning (≤ 5 km) | clear — thresholds from constraints.yaml H2."""
    if beyond:
        return "beyond"
    r = _rings()
    if distance_km <= r["alarm"]:
        return "alarm"
    if distance_km <= r["warning"]:
        return "warning"
    return "clear"


def _source(ly: layers.Layers) -> str:
    return f"{ly.imbl_props['source']}; {ly.mpa_props['source']}"


def fence_check(lat: float, lon: float) -> dict[str, Any]:
    """Distance to the India–Sri Lanka border line (IMBL) and whether the point is inside the Gulf of
    Mannar marine park, for one position.

    Returns imbl_km (km to the line, 0.1 km precision), side ("india" or "beyond_imbl"), ring
    ("clear" > 5 km, "warning" ≤ 5 km, "alarm" ≤ 2 km, "beyond"), in_mpa (park + eco-sensitive zone).
    Coordinates must be inside the region (lat 8.0–10.5, lon 78.0–80.5).
    """
    qc.check_region(lat, lon)
    ly = layers.load()
    p = layers.point_m(lat, lon)
    beyond = not ly.india_side.contains(p)
    km = round(ly.imbl.distance(p) / 1000.0, 1)
    in_mpa = ly.mpa_prepared.contains(p)
    return ToolResult(
        data={
            "imbl_km": km,
            "side": "beyond_imbl" if beyond else "india",
            "ring": ring_for(km, beyond),
            "in_mpa": in_mpa,
            "mpa_name": ly.mpa_props["name"] if in_mpa else None,
            "cell": h3.latlng_to_cell(lat, lon, 7),
        },
        source=_source(ly),
        source_url=ly.imbl_props["source_url"][0],
        fetched_at=now(),
        confidence="high",
        notes=["marine park layer includes its eco-sensitive zone (conservative)"],
    ).model_dump(mode="json")


def geo_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> dict[str, Any]:
    """Great-circle distance (km, 0.1 km precision; also nautical miles) and initial bearing
    (degrees from north, plus an 8-point compass word) from point 1 to point 2 on the WGS84 ellipsoid.
    """
    for la, lo in ((lat1, lon1), (lat2, lon2)):
        qc.check_region(la, lo)
    az, _, metres = _GEOD.inv(lon1, lat1, lon2, lat2)
    bearing = az % 360.0
    return ToolResult(
        data={
            "km": round(metres / 1000.0, 1),
            "nm": round(metres / 1852.0, 1),
            "bearing_deg": round(bearing),
            "direction": COMPASS[int((bearing + 22.5) // 45) % 8],
        },
        source="computed (WGS84 geodesic)",
        source_url="urn:tarangyukti:geodesic",
        fetched_at=now(),
        confidence="high",
    ).model_dump(mode="json")


@cached(
    ns="layer",
    ttl=config.ttl("layers"),
    key=lambda cell: fingerprint("cell_fence", layers.load().version, config.constraints()["version"], cell),
    tags=lambda cell: [f"cell:{cell}", "layer:fence"],
)
async def cell_fence(cell: str) -> dict[str, Any]:
    """Fence flags for a whole H3 cell: min km from any part of it to the IMBL, crosses or lies beyond the
    IMBL, touches the marine park, centre on land. Route search removes cells that fail H2/H3."""
    f = layers.fence_flags(cell)
    return {
        "cell": cell,
        "imbl_min_km": f.imbl_min_km,
        "beyond_or_crossing": f.beyond_or_crossing,
        "touches_mpa": f.touches_mpa,
        "land": f.land,
        "layer_version": layers.load().version[:12],
    }
