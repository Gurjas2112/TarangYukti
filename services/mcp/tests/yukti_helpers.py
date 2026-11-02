"""Synthetic contexts for engine tests: real map layers, made-up weather and alerts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import h3

from tarangyukti import config, layers
from tarangyukti.tools.alert_model import Warning_
from tarangyukti.yukti.model import Ctx, InputInfo, Weather
from tarangyukti.yukti.sun import sunset_utc

T0 = datetime(2026, 11, 3, 0, 0, tzinfo=UTC)  # 05:30 IST
HARBOUR = h3.latlng_to_cell(9.288, 79.313, 7)  # Rameswaram
PALK_BAY = h3.latlng_to_cell(9.55, 79.30, 7)
BEYOND_IMBL = h3.latlng_to_cell(9.45, 79.48, 7)
NEAR_HARBOUR_BOX = {
    "type": "Polygon",
    "coordinates": [[[79.15, 9.15], [79.5, 9.15], [79.5, 9.45], [79.15, 9.45], [79.15, 9.15]]],
}


@dataclass
class Sea:
    """Calm sea with optional storms: (start, end, wave_m, wind_kmh) applied everywhere."""

    wave_m: float = 0.5
    wind_kmh: float = 10.0
    storms: list[tuple[datetime, datetime, float, float]] = field(default_factory=list)
    horizon: datetime = T0 + timedelta(hours=72)

    def __call__(self, cell: str, at: datetime) -> Weather | None:
        if at > self.horizon:
            return None
        for a, b, w, u in self.storms:
            if a <= at <= b:
                return Weather(w, u)
        return Weather(self.wave_m, self.wind_kmh)


def inputs(fetched_at: datetime = T0) -> list[InputInfo]:
    return [
        InputInfo("forecast", "waves", "test forecast", "urn:test", fetched_at, True),
        InputInfo("warnings_imd", "warnings", "test IMD", "urn:test", fetched_at, True),
        InputInfo("warnings_incois", "warnings", "test INCOIS", "urn:test", fetched_at, True),
        InputInfo("warnings_sdma", "warnings", "test SDMA", "urn:test", fetched_at, True),
    ]


def make_ctx(
    boat_type: str = "small_frp",
    weather: Callable[[str, datetime], Weather | None] | None = None,
    warnings: list[Warning_] | None = None,
    boat_overrides: dict[str, Any] | None = None,
    as_of: datetime = T0,
    inp: list[InputInfo] | None = None,
) -> Ctx:
    boat = dict(config.load("boats.yaml")[boat_type]) | (boat_overrides or {})
    lat0, lon0 = h3.cell_to_latlng(HARBOUR)
    return Ctx(
        as_of=as_of,
        boat_type=boat_type,
        boat=boat,
        params=config.constraints(),
        weather=weather or Sea(),
        fence=layers.fence_flags,
        warnings=warnings or [],
        inputs=inp if inp is not None else inputs(as_of),
        sunset=lambda d: sunset_utc(d, lat0, lon0),
        region_names=tuple(config.qc()["region"]["alert_area_names"]),
    )


def warning(
    start: datetime,
    hours: float,
    kind: str = "high_wave",
    issuer: str = "INCOIS",
    area: dict[str, Any] | None = NEAR_HARBOUR_BOX,
    wid: str = "W1",
    **kw: Any,
) -> Warning_:
    return Warning_(
        id=wid,
        issuer=issuer,  # type: ignore[arg-type]
        kind=kind,
        title=f"Test {kind} alert",
        event=kind,
        area=area,
        valid_from=start,
        valid_to=start + timedelta(hours=hours),
        issued_at=start - timedelta(hours=1),
        severity="warning",
        source_url="urn:test",
        **kw,
    )


def with_boat(ctx: Ctx, **overrides: Any) -> Ctx:
    return replace(ctx, boat=ctx.boat | overrides)
