"""Yukti engine and route search (Milestone 3): constraint behaviour, earliest window, outcome mapping."""

from __future__ import annotations

from datetime import date, timedelta

import h3
import pytest

from tarangyukti import layers, route
from tarangyukti.yukti import engine
from tarangyukti.yukti.constraints import REGISTRY
from tarangyukti.yukti.sun import sunset_utc

from .yukti_helpers import BEYOND_IMBL, HARBOUR, PALK_BAY, T0, Sea, inputs, make_ctx, warning


def ids(ev: engine.Evaluation) -> dict[str, bool]:
    return {e.id: e.ok for e in ev.ledger}


def test_catalogue_complete() -> None:
    assert set(REGISTRY) == {f"H{i}" for i in range(1, 9)} | {f"S{i}" for i in range(1, 6)}


def test_calm_local_trip_is_go() -> None:
    ctx = make_ctx()
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0))
    assert ev.outcome == "GO"
    assert all(ok for cid, ok in ids(ev).items() if cid.startswith("H"))
    assert ev.risk is not None and ev.risk < 0.6


def test_moderate_wind_is_caution() -> None:
    ctx = make_ctx(weather=Sea(wave_m=0.5, wind_kmh=24.0))  # 24/30 = 0.8 ≥ 0.6
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0))
    assert ev.outcome == "CAUTION"
    assert ids(ev)["S3"] is False


def test_high_waves_no_go_and_no_window() -> None:
    ctx = make_ctx(weather=Sea(wave_m=2.0))  # small FRP limit 1.5 m
    plan = engine.plan_trip(ctx, HARBOUR, None)
    assert plan.requested.outcome == "NO-GO"
    assert "H5" in plan.requested.failed_hard()
    assert plan.earliest is None and plan.best is None


def test_earliest_window_after_storm() -> None:
    storm = (T0, T0 + timedelta(hours=6), 2.4, 40.0)
    ctx = make_ctx(weather=Sea(storms=[storm]))
    plan = engine.plan_trip(ctx, HARBOUR, None)
    assert plan.requested.outcome == "NO-GO"
    assert plan.earliest is not None
    assert plan.earliest.candidate.depart > storm[1]  # the whole trip is after the storm
    assert plan.earliest.outcome in ("GO", "CAUTION")


def test_official_warning_blocks_and_is_cited() -> None:
    w = warning(T0 - timedelta(hours=1), 12, wid="INCOIS-HW-9", simulation=True)
    ctx = make_ctx(warnings=[w])
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0))
    h1 = next(e for e in ev.ledger if e.id == "H1")
    assert ev.outcome == "NO-GO" and not h1.ok
    assert h1.evidence == ("INCOIS-HW-9",)
    assert "SIMULATION" in h1.detail


def test_sdma_alert_blocks_too() -> None:
    ctx = make_ctx(warnings=[warning(T0, 12, kind="cyclone", issuer="SDMA")])
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0))
    assert "H1" in ev.failed_hard()


def test_warning_elsewhere_or_later_does_not_block_now() -> None:
    far = {"type": "Polygon", "coordinates": [[[80.0, 15.0], [80.3, 15.0], [80.3, 15.3], [80.0, 15.3], [80.0, 15.0]]]}
    ctx = make_ctx(warnings=[warning(T0, 12, area=far), warning(T0 + timedelta(days=1), 6, wid="W2")])
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0))
    assert ev.feasible


def test_alert_without_polygon_naming_region_covers_it() -> None:
    w = warning(T0, 12, area=None, sectors=["Ramanathapuram"], area_desc="Ramanathapuram coast")
    ctx = make_ctx(warnings=[w])
    assert "H1" in engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0)).failed_hard()


def test_thunderstorm_is_h7_not_h1() -> None:
    ctx = make_ctx(warnings=[warning(T0, 3, kind="thunderstorm", issuer="IMD")])
    failed = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0)).failed_hard()
    assert failed == ["H7"]


def test_ban_season_for_mechanised_only() -> None:
    in_ban = T0.replace(month=5, day=10)
    trawler = make_ctx("mechanised_trawler", as_of=in_ban, weather=Sea(horizon=in_ban + timedelta(days=3)))
    assert "H4" in engine.evaluate(trawler, engine.candidate(trawler, HARBOUR, None, in_ban)).failed_hard()
    canoe = make_ctx("non_motorised", as_of=in_ban, weather=Sea(horizon=in_ban + timedelta(days=3)))
    assert "H4" not in engine.evaluate(canoe, engine.candidate(canoe, HARBOUR, None, in_ban)).failed_hard()


def test_stale_forecast_is_never_go() -> None:
    ctx = make_ctx(inp=inputs(T0 - timedelta(hours=7)))  # waves limit 6 h, warnings 1 h
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0))
    h8 = next(e for e in ev.ledger if e.id == "H8")
    assert ev.outcome == "NO-GO" and not h8.ok and h8.unknown
    assert "forecast 7.0 h old" in h8.detail


def test_missing_input_is_never_go() -> None:
    ctx = make_ctx(inp=[i for i in inputs() if i.name != "warnings_incois"])
    assert "H8" in engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0)).failed_hard()


def test_no_forecast_is_unknown_not_go() -> None:
    ctx = make_ctx(weather=Sea(horizon=T0 + timedelta(hours=2)))  # trip outlives the forecast
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0))
    h5 = next(e for e in ev.ledger if e.id == "H5")
    assert ev.outcome == "NO-GO" and h5.unknown and h5.value == "unknown"


def test_route_to_palk_bay() -> None:
    ctx = make_ctx()
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, PALK_BAY, T0))
    assert ev.feasible
    c = ev.candidate
    assert c.goal_cell == PALK_BAY and c.route_km > 0
    assert c.timeline[0].cell == HARBOUR and c.timeline[-1].cell == HARBOUR  # out and back
    assert c.return_at > c.depart


def test_goal_beyond_imbl_is_unreachable() -> None:
    ctx = make_ctx()
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, BEYOND_IMBL, T0))
    h2 = [e for e in ev.ledger if e.id == "H2"]
    assert len(h2) == 1 and not h2[0].ok and h2[0].value == "no route"
    assert ev.outcome == "NO-GO"


def test_route_avoids_removed_cells() -> None:
    ctx = make_ctx()
    path = route.astar(ctx, HARBOUR, PALK_BAY, T0)
    assert path is not None
    for s in path.stops[1:-1]:
        assert not route.removed(ctx, s.cell, set())
    assert all(b.at >= a.at for a, b in zip(path.stops, path.stops[1:], strict=False))


def test_fuel_margin_soft_warning() -> None:
    ctx = make_ctx("non_motorised")  # range 20 km → 16 km allowed
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, PALK_BAY, T0))
    s2 = next(e for e in ev.ledger if e.id == "S2")
    assert not s2.ok
    assert "S2" not in ev.failed_hard()  # soft: lowers rank, does not refuse


def test_sunset_for_small_boats() -> None:
    late = T0 + timedelta(hours=8)  # 13:30 IST + 8 h local trip → after sunset
    small = make_ctx("small_frp")
    s4 = next(e for e in engine.evaluate(small, engine.candidate(small, HARBOUR, None, late)).ledger if e.id == "S4")
    assert not s4.ok
    trawler = make_ctx("mechanised_trawler")
    s4t = next(
        e for e in engine.evaluate(trawler, engine.candidate(trawler, HARBOUR, None, late)).ledger if e.id == "S4"
    )
    assert s4t.ok and s4t.value == "not applicable"


def test_sunset_rameswaram_november() -> None:
    lat, lon = h3.cell_to_latlng(HARBOUR)
    s = sunset_utc(date(2026, 11, 3), lat, lon)
    ist = s + timedelta(hours=5, minutes=30)
    assert (ist.hour, ist.minute // 10) in ((17, 4), (17, 5))  # about 17:45–17:55 IST


def test_departures_every_30_min_for_24_h() -> None:
    ctx = make_ctx()
    times = engine.departures(ctx, T0 + timedelta(minutes=7))
    assert times[0] == T0 + timedelta(minutes=30)
    assert len(times) == 49 and times[-1] - times[0] == timedelta(hours=24)


def test_harbour_is_land_but_routable() -> None:
    assert layers.fence_flags(HARBOUR).land
    assert route.astar(make_ctx(), PALK_BAY, HARBOUR, T0) is not None


@pytest.mark.parametrize("outcome", ["GO", "CAUTION", "NO-GO"])
def test_outcome_mapping(outcome: str) -> None:
    sea = {"GO": Sea(), "CAUTION": Sea(wind_kmh=24.0), "NO-GO": Sea(wave_m=3.0)}[outcome]
    ctx = make_ctx(weather=sea)
    assert engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0)).outcome == outcome
