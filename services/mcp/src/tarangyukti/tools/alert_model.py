"""The normalised official-warning record shared by the CAP reader, snapshots and the warning tools."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Issuer = Literal["IMD", "INCOIS"]
AnyIssuer = Literal["IMD", "INCOIS", "SDMA"]  # SDMA: a state authority alert citing neither
Severity = Literal["warning", "alert", "watch"]


class Warning_(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    issuer: AnyIssuer
    kind: str  # high_wave, storm_surge, cyclone, thunderstorm, strong_wind, heavy_rain, …
    title: str
    event: str | None = None  # CAP <event>, as issued
    cap_severity: str | None = None  # CAP <severity>: Extreme | Severe | Moderate | Minor | Unknown
    office: str | None = None  # who disseminated it on SACHET, e.g. "IMD Chennai", "Tamil Nadu SDMA"
    area_desc: str | None = None  # CAP <areaDesc>, as issued
    districts: list[str] = []
    sectors: list[str] = []
    area: dict[str, Any] | None = None  # GeoJSON (Multi)Polygon, lon/lat, simplified
    valid_from: datetime
    valid_to: datetime
    issued_at: datetime
    severity: Severity
    simulation: bool = False
    instruction: str | None = None  # CAP <instruction>, as issued
    references: list[str] = []  # CAP identifiers of earlier alerts this one updates or replaces
    source_url: str


def active(warnings: list[Warning_], at: datetime) -> list[Warning_]:
    return [w for w in warnings if w.valid_from <= at <= w.valid_to]
