"""Yukti invariants (Milestone 3, spec §14.2), checked with Hypothesis over random weather and alerts.

1. A new warning never makes a trip safer.
2. Tightening a boat limit never adds departure windows.
3. Every refusal has a failed hard constraint (and every GO has none).
4. The route never enters removed cells or bad-weather time steps.
"""

from __future__ import annotations

from datetime import timedelta

import h3
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tarangyukti import route
from tarangyukti.yukti import engine
from tarangyukti.yukti.model import Ctx, Evaluation, Weather

from .yukti_helpers import HARBOUR, NEAR_HARBOUR_BOX, PALK_BAY, T0, Sea, make_ctx, warning, with_boat

DEPARTURES = [T0 + timedelta(hours=h) for h in (0, 3, 6, 9, 12, 18)]
FAST = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])

storms = st.lists(
    st.tuples(
        st.integers(0, 30),  # start hour
        st.integers(1, 12),  # duration
        st.floats(0.0, 3.5),  # waves
        st.floats(0.0, 60.0),  # wind
    ),
    max_size=3,
)


def sea_from(spec: list[tuple[int, int, float, float]], wave: float, wind: float) -> Sea:
    return Sea(
        wave_m=wave,
        wind_kmh=wind,
        storms=[(T0 + timedelta(hours=a), T0 + timedelta(hours=a + d), w, u) for a, d, w, u in spec],
    )


def outcomes(ctx: Ctx, goal: str | None = None) -> list[Evaluation]:
    return [engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, goal, t)) for t in DEPARTURES]


@FAST
@given(
    spec=storms,
    wave=st.floats(0.0, 2.0),
    wind=st.floats(0.0, 35.0),
    start_h=st.integers(-6, 30),
    hours=st.integers(1, 24),
    kind=st.sampled_from(["high_wave", "cyclone", "thunderstorm", "storm_surge"]),
    issuer=st.sampled_from(["IMD", "INCOIS", "SDMA"]),
)
def test_new_warning_never_makes_trip_safer(
    spec: list[tuple[int, int, float, float]],
    wave: float,
    wind: float,
    start_h: int,
    hours: int,
    kind: str,
    issuer: str,
) -> None:
    sea = sea_from(spec, wave, wind)
    before = outcomes(make_ctx(weather=sea))
    w = warning(T0 + timedelta(hours=start_h), hours, kind=kind, issuer=issuer, area=NEAR_HARBOUR_BOX)
    after = outcomes(make_ctx(weather=sea, warnings=[w]))
    for b, a in zip(before, after, strict=True):
        assert engine.RANK[a.outcome] >= engine.RANK[b.outcome]
        assert not (a.feasible and not b.feasible)


@FAST
@given(spec=storms, wave=st.floats(0.0, 2.0), wind=st.floats(0.0, 35.0), factor=st.floats(0.3, 1.0))
def test_tightening_a_limit_never_adds_windows(
    spec: list[tuple[int, int, float, float]], wave: float, wind: float, factor: float
) -> None:
    ctx = make_ctx(weather=sea_from(spec, wave, wind))
    tight = with_boat(ctx, max_wave_m=ctx.boat["max_wave_m"] * factor, max_wind_kmh=ctx.boat["max_wind_kmh"] * factor)
    loose_ok = {e.candidate.depart for e in outcomes(ctx) if e.feasible}
    tight_ok = {e.candidate.depart for e in outcomes(tight) if e.feasible}
    assert tight_ok <= loose_ok


@FAST
@given(
    spec=storms,
    wave=st.floats(0.0, 3.0),
    wind=st.floats(0.0, 50.0),
    boat=st.sampled_from(["non_motorised", "small_frp", "mechanised_trawler"]),
    with_alert=st.booleans(),
)
def test_every_refusal_names_a_failed_hard_constraint(
    spec: list[tuple[int, int, float, float]], wave: float, wind: float, boat: str, with_alert: bool
) -> None:
    ws = [warning(T0 + timedelta(hours=2), 6)] if with_alert else []
    ctx = make_ctx(boat, weather=sea_from(spec, wave, wind), warnings=ws)
    for ev in outcomes(ctx):
        if ev.outcome == "NO-GO":
            assert ev.failed_hard(), "a NO-GO must name the hard constraint that failed"
        else:
            assert not ev.failed_hard()
            assert ev.risk is not None
            assert (ev.outcome == "CAUTION") == (ev.risk >= float(ctx.soft("S3")["caution_at"]))


@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    band_lat=st.floats(9.33, 9.5),
    band_wave=st.floats(0.0, 3.0),
    depart_h=st.integers(0, 12),
)
def test_route_never_enters_removed_or_bad_weather_cells(band_lat: float, band_wave: float, depart_h: int) -> None:
    """A band of rough sea across Palk Bay: the route goes around it, or there is no route."""

    def weather(cell: str, at: object) -> Weather:
        lat, _ = h3.cell_to_latlng(cell)
        return Weather(band_wave if abs(lat - band_lat) < 0.03 else 0.4, 10.0)

    ctx = make_ctx(weather=weather)
    depart = T0 + timedelta(hours=depart_h)
    path = route.astar(ctx, HARBOUR, PALK_BAY, depart)
    if path is None:
        return
    for s in path.stops[1:-1]:
        assert not route.removed(ctx, s.cell, set())
        assert not route.weather_blocked(ctx, s.cell, s.at)
