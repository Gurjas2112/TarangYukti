"""Quality checks before any tool returns (spec §9.3 layers 2–3, thresholds in config/qc.yaml)."""

from __future__ import annotations

import math
from datetime import datetime

from . import config


class OutOfRegion(ValueError):
    pass


def bbox() -> dict[str, float]:
    b: dict[str, float] = config.qc()["region"]["bbox"]
    return b


def check_region(lat: float, lon: float) -> None:
    """Reject coordinates outside the prototype region (Gulf of Mannar + Palk Bay)."""
    b = bbox()
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise OutOfRegion("coordinates must be finite numbers")
    if not (b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]):
        raise OutOfRegion(
            f"outside the covered region (lat {b['lat_min']}–{b['lat_max']}, lon {b['lon_min']}–{b['lon_max']})"
        )


def in_range(kind: str, value: float | None) -> float | None:
    """Value if inside its plausible range, else None (marked missing, never interpolated)."""
    if value is None or not math.isfinite(value):
        return None
    r = config.qc()["ranges"][kind]
    if "min" in r and value < r["min"]:
        return None
    if "max" in r and value > r["max"]:
        return None
    return value


def age_hours(then: datetime, now: datetime) -> float:
    return round((now - then).total_seconds() / 3600.0, 1)


def freshness_limit_h(kind: str) -> float:
    return float(config.qc()["freshness_h"][kind])
