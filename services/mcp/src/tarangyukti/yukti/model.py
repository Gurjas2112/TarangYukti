"""Value types for the Yukti engine. Pure data: no I/O."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from ..layers import FenceFlags
from ..tools.alert_model import Warning_

Outcome = Literal["GO", "CAUTION", "NO-GO"]


@dataclass(frozen=True)
class Weather:
    wave_m: float | None
    wind_kmh: float | None


@dataclass(frozen=True)
class InputInfo:
    """Provenance of one input, for H8 and the ledger (Observation.known_at / Dataset)."""

    name: str  # "forecast", "warnings_imd", "warnings_incois", "warnings_sdma", "pfz"
    kind: str  # key into H8 max_age_h: waves | warnings | pfz
    source: str
    source_url: str
    fetched_at: datetime  # → known_at
    available: bool
    cache: str = "miss"


@dataclass(frozen=True)
class Stop:
    cell: str
    at: datetime


@dataclass(frozen=True)
class Candidate:
    """One trip option: a departure time and the cells the boat is in, hour by hour."""

    depart: datetime
    return_at: datetime
    timeline: tuple[Stop, ...]
    start_cell: str
    goal_cell: str | None = None  # None = local trip around the harbour
    route_km: float = 0.0  # round trip
    route_found: bool = True  # False: no path avoids the removed cells; timeline is start → goal only
    notes: tuple[str, ...] = ()

    @property
    def cells(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(s.cell for s in self.timeline))


@dataclass(frozen=True)
class Verdict:
    ok: bool
    value: float | str | None = None
    unit: str | None = None
    evidence: tuple[str, ...] = ()  # input names / warning ids / layer ids
    detail: str = ""
    at: datetime | None = None  # when the deciding value is true (→ Observation.valid_at)
    unknown: bool = False  # data missing: counts as a failure for hard constraints (never GO)


@dataclass(frozen=True)
class LedgerEntry:
    id: str
    kind: Literal["hard", "soft"]
    name: str
    ok: bool
    value: float | str | None
    unit: str | None
    evidence: tuple[str, ...]
    detail: str
    at: datetime | None
    unknown: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "ok": self.ok,
            "value": self.value,
            "unit": self.unit,
            "evidence": list(self.evidence),
            "detail": self.detail,
            "at": self.at.isoformat() if self.at else None,
            "unknown": self.unknown,
        }


@dataclass(frozen=True)
class Evaluation:
    candidate: Candidate
    outcome: Outcome
    feasible: bool
    risk: float | None
    score: float
    ledger: tuple[LedgerEntry, ...]

    def failed_hard(self) -> list[str]:
        return [e.id for e in self.ledger if e.kind == "hard" and not e.ok]


@dataclass
class Ctx:
    """Everything the constraints may look at. Built by facts.py (I/O) or by tests (synthetic)."""

    as_of: datetime
    boat_type: str
    boat: dict[str, Any]  # config/boats.yaml entry
    params: dict[str, Any]  # config/constraints.yaml
    weather: Callable[[str, datetime], Weather | None]
    fence: Callable[[str], FenceFlags]
    warnings: list[Warning_] = field(default_factory=list)
    inputs: list[InputInfo] = field(default_factory=list)
    sunset: Callable[[date], datetime] | None = None
    pfz_points: list[tuple[float, float]] = field(default_factory=list)  # (lat, lon)
    region_names: tuple[str, ...] = ()  # alert area names that mean "our region"

    @property
    def speed_kmh(self) -> float:
        return float(self.boat["speed_knots"]) * 1.852

    def hard(self, cid: str) -> dict[str, Any]:
        h: dict[str, Any] = self.params["hard"][cid]
        return h

    def soft(self, cid: str) -> dict[str, Any]:
        s: dict[str, Any] = self.params["soft"][cid]
        return s
