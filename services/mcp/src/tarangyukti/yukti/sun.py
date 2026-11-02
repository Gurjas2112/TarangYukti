"""Sunset time (NOAA solar position algorithm, about one-minute accuracy) for S4 — no API needed."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta


def sunset_utc(day: date, lat: float, lon: float) -> datetime:
    """UTC time of sunset (sun centre 0.833° below the horizon) on `day` at (lat, lon)."""
    n = day.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (n - 1 + 0.5)  # fractional year at local noon
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    phi = math.radians(lat)
    cos_ha = math.cos(math.radians(90.833)) / (math.cos(phi) * math.cos(decl)) - math.tan(phi) * math.tan(decl)
    ha = math.degrees(math.acos(max(-1.0, min(1.0, cos_ha))))
    minutes = 720 - 4 * (lon - ha) - eqtime  # sunset: hour angle is positive
    return datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(minutes=minutes)
