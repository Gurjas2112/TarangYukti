"""Trip and border-alert rules shared by channels (live positions) and the worker (safety-net sweep).

Pure functions (no I/O, no clock), so they are tested with fixed times (prompt §10.5-10.7, spec §6.6, §17.4).
Distances to the border line come from the fence_check tool; thresholds come from config (constraints.yaml H2
alert rings, harbours.yaml geofence radius).
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

import yaml

from .settings import find_config_dir

REPEAT_GAP = timedelta(hours=2)
Rule = Literal["border-5km", "border-2km", "beyond-imbl", "mpa"]
RULE_LEVEL: dict[str, int] = {"mpa": 0, "border-5km": 1, "border-2km": 2, "beyond-imbl": 3}


@functools.cache
def _yaml(name: str) -> dict[str, Any]:
    doc: dict[str, Any] = yaml.safe_load((find_config_dir() / name).read_text(encoding="utf-8"))
    return doc


def geofence_m() -> float:
    return float(_yaml("harbours.yaml").get("geofence_m", 1500))


def alert_rings_km() -> dict[str, float]:
    rings = _yaml("constraints.yaml")["hard"]["H2"]["alert_rings_km"]
    return {"warning": float(rings["warning"]), "alarm": float(rings["alarm"])}


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def at_harbour(lat: float, lon: float, harbour: dict[str, Any]) -> bool:
    return km_between(lat, lon, float(harbour["lat"]), float(harbour["lon"])) * 1000 <= geofence_m()


def transition(trip_open: bool, inside_harbour: bool) -> Literal["open", "close"] | None:
    """Leaving the harbour circle opens a trip; re-entering closes it (closed_by='geofence')."""
    if not trip_open and not inside_harbour:
        return "open"
    if trip_open and inside_harbour:
        return "close"
    return None


def fence_rules(imbl_km: float, beyond: bool, in_mpa: bool) -> list[Rule]:
    """Alert rules for one position: the strongest border ring that applies (5 km warning, 2 km alarm, or past the
    line) and the marine park."""
    rings = alert_rings_km()
    out: list[Rule] = []
    if beyond:
        out.append("beyond-imbl")
    elif imbl_km <= rings["alarm"]:
        out.append("border-2km")
    elif imbl_km <= rings["warning"]:
        out.append("border-5km")
    if in_mpa:
        out.append("mpa")
    return out


@dataclass(frozen=True)
class Sent:
    rule: str
    at: datetime


def should_alert(rule: str, now: datetime, recent: list[Sent]) -> bool:
    """De-duplicate per boat: the same rule at most once per 2 hours, unless the level rose since the last border
    alert (5 km → 2 km → past the line always alerts)."""
    window = [s for s in recent if now - s.at < REPEAT_GAP]
    if any(s.rule == rule for s in window):
        return False
    if rule == "mpa":
        return True
    higher = [s for s in window if s.rule != "mpa" and RULE_LEVEL.get(s.rule, 0) >= RULE_LEVEL[rule]]
    return not higher


def right_on(feedback: list[str | None], days: int = 30) -> tuple[int, int]:
    """("right" count, answered count) over the last `days` closed trips with feedback."""
    answered = [f for f in feedback[:days] if f in ("right", "wrong")]
    return sum(1 for f in answered if f == "right"), len(answered)
