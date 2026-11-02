"""Tool contract tests: online (respx-mocked), cached, stale, snapshot, QC (prompt §16 "Tool contract")."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import httpx
import orjson
import pytest
import respx
from ty_common.cache import Cache
from ty_common.models import ToolResult
from ty_common.settings import get_settings

from tarangyukti import qc
from tarangyukti.tools import grids, marine, warnings
from tarangyukti.tools.common import freeze

from .conftest import NOW, erddap, make_snapshot, marine_payload, warning, wind_payload

MARINE = "https://marine-api.open-meteo.com/v1/marine"
WIND = "https://api.open-meteo.com/v1/forecast"
LAT, LON = 9.20, 79.40


def mock_open_meteo(waves: list[float | None], wind: float = 14.0) -> None:
    respx.get(MARINE).mock(return_value=httpx.Response(200, json=marine_payload(9.21, 79.38, waves)))
    respx.get(WIND).mock(return_value=httpx.Response(200, json=wind_payload(9.21, 79.38, len(waves), wind)))


# ── marine_forecast ──────────────────────────────────────────────────────────────


@respx.mock
async def test_marine_online_then_cached() -> None:
    mock_open_meteo([0.4, 0.5, 0.6])
    r = await marine.marine_forecast(LAT, LON, 3)
    ToolResult.model_validate_json(orjson.dumps(r))  # the wire format is JSON
    assert r["cache"] == "miss"
    assert r["confidence"] == "high"
    assert [h["wave_m"] for h in r["data"]["hours"]] == [0.4, 0.5, 0.6]
    assert r["data"]["hours"][0]["wind_kmh"] == 14.0
    assert r["data"]["hours"][0]["time"] == "2026-11-02T03:00:00Z"
    assert r["valid_at"].startswith("2026-11-02T03:00")
    calls = respx.calls.call_count
    again = await marine.marine_forecast(LAT + 0.001, LON, 3)  # same H3 cell
    assert again["cache"] == "hit"
    assert respx.calls.call_count == calls


@respx.mock
async def test_marine_new_hour_is_new_key() -> None:
    mock_open_meteo([0.4])
    await marine.marine_forecast(LAT, LON, 1)
    freeze(NOW + timedelta(hours=1))
    r = await marine.marine_forecast(LAT, LON, 1)
    assert r["cache"] == "miss"


@respx.mock
async def test_marine_qc_marks_out_of_range_missing() -> None:
    mock_open_meteo([0.4, 25.0], wind=400.0)
    r = await marine.marine_forecast(LAT, LON, 2)
    assert r["data"]["hours"][1]["wave_m"] is None
    assert r["data"]["hours"][0]["wind_kmh"] is None
    assert any("outside plausible ranges" in n for n in r["notes"])


@respx.mock
async def test_marine_land_cell_low_confidence() -> None:
    mock_open_meteo([None, None])
    r = await marine.marine_forecast(LAT, LON, 2)
    assert r["confidence"] == "low"
    assert any("no wave data" in n for n in r["notes"])


@respx.mock
async def test_marine_live_down_falls_back_to_snapshot(env: Path) -> None:
    make_snapshot(env)
    respx.get(MARINE).mock(return_value=httpx.Response(503))
    r = await marine.marine_forecast(9.26, 79.49, 4)
    assert r["cache"] == "snapshot"
    assert r["confidence"] == "low"
    assert any("live source unavailable" in n for n in r["notes"])
    assert r["data"]["hours"][0]["wave_m"] == 0.6


@respx.mock
async def test_marine_live_down_no_snapshot_is_unavailable() -> None:
    respx.get(MARINE).mock(return_value=httpx.Response(503))
    r = await marine.marine_forecast(LAT, LON, 2)
    assert r["data"]["available"] is False
    assert r["confidence"] == "low"


async def test_marine_snapshot_mode_never_calls_network(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_snapshot(env)
    monkeypatch.setattr(get_settings(), "data_mode", "snapshot")
    with respx.mock(assert_all_called=False) as router:
        route = router.route().mock(side_effect=AssertionError("network used in snapshot mode"))
        r = await marine.marine_forecast(9.26, 79.49, 6)
        assert not route.called
    assert r["cache"] == "snapshot"
    assert r["fetched_at"].startswith("2026-11-02T02:00")  # snapshot capture time, not now
    assert len(r["data"]["hours"]) == 6
    assert r["data"]["hours"][0]["time"] == "2026-11-02T03:00:00Z"  # starts at the current hour


async def test_snapshot_mode_skips_land_grid_points(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_snapshot(env)
    monkeypatch.setattr(get_settings(), "data_mode", "snapshot")
    r = await marine.marine_forecast(9.25, 79.27, 2)  # nearest grid point is land; next one is sea
    assert r["data"]["hours"][0]["wave_m"] == 0.6


@respx.mock
async def test_stale_if_error(cache: Cache) -> None:
    mock_open_meteo([0.4])
    await marine.marine_forecast(LAT, LON, 1)
    for k in [k async for k in cache.redis.scan_iter("tool:*")]:
        await cache.redis.delete(k)  # fresh copies expire; lastgood stays
    cache.l1.clear()
    respx.get(MARINE).mock(side_effect=httpx.ConnectError("down"))
    r = await marine.marine_forecast(LAT, LON, 1)
    assert r["cache"] == "stale"
    assert r["data"]["hours"][0]["wave_m"] == 0.4


def test_out_of_region_rejected() -> None:
    with pytest.raises(qc.OutOfRegion):
        qc.check_region(13.08, 80.27)  # Chennai


async def test_marine_out_of_region_raises() -> None:
    with pytest.raises(qc.OutOfRegion):
        await marine.marine_forecast(13.08, 80.27)


@respx.mock
async def test_no_coordinates_in_cache(cache: Cache) -> None:
    """Prompt §7a: caches key by H3 cell; no raw coordinates in any cached value."""
    mock_open_meteo([0.4])
    await marine.marine_forecast(9.20123, 79.40456, 1)
    for k in [k async for k in cache.redis.scan_iter("*")]:
        if (await cache.redis.type(k)) != b"string":
            continue
        blob = await cache.redis.get(k)
        assert b"9.20123" not in blob and b"79.40456" not in blob
        assert b"latitude" not in blob


# ── grids ────────────────────────────────────────────────────────────────────────


@respx.mock
async def test_sst_grid_stats_and_masks() -> None:
    respx.get(url__startswith="https://coastwatch.pfeg.noaa.gov/").mock(
        return_value=httpx.Response(
            200, json=erddap("sst", [(9.125, 79.125, 29.8), (9.375, 79.375, 30.2), (9.6, 79.6, None), (9.7, 79.7, 50)])
        )
    )
    r = await grids.sst_grid()
    s = r["data"]["stats"]
    assert (s["min"], s["max"], s["valid_points"]) == (29.8, 30.2, 2)
    assert s["masked_fraction"] == 0.25
    assert any("outside plausible range" in n for n in r["notes"])
    assert r["data"]["age_hours"] == 15.0
    assert r["confidence"] == "medium"  # half the cells masked or rejected


@respx.mock
async def test_chl_grid_old_data_flagged() -> None:
    respx.get(url__startswith="https://coastwatch.noaa.gov/").mock(
        return_value=httpx.Response(200, json=erddap("chlor_a", [(9.1, 79.1, 1.2)], when="2026-10-29T12:00:00Z"))
    )
    r = await grids.chl_grid(9.0, 9.5, 79.0, 79.5)
    assert r["data"]["age_hours"] == 87.0
    assert any("old (limit 48.0 h)" in n for n in r["notes"])
    assert r["confidence"] == "medium"


@respx.mock
async def test_grid_all_masked_unavailable() -> None:
    respx.get(url__startswith="https://coastwatch.noaa.gov/").mock(
        return_value=httpx.Response(200, json=erddap("chlor_a", [(9.1, 79.1, None)]))
    )
    r = await grids.chl_grid()
    assert r["data"]["available"] is False


async def test_grid_bbox_must_be_inside_region() -> None:
    with pytest.raises(qc.OutOfRegion):
        await grids.sst_grid(7.0, 9.0, 79.0, 80.0)


# ── warnings and PFZ ─────────────────────────────────────────────────────────────


async def test_incois_alerts_active_and_place_filter(env: Path) -> None:
    make_snapshot(env)
    r = await warnings.incois_alerts("ramanathapuram")
    assert r["data"]["count"] == 1
    assert r["cache"] == "snapshot"  # online has no feed → snapshot
    other = await warnings.incois_alerts("Nagapattinam")
    assert other["data"]["count"] == 0


async def test_expired_warning_not_active(env: Path) -> None:
    store = make_snapshot(env)
    store.write(
        "warnings_incois",
        {"warnings": [warning(valid_to="2026-11-02T02:00:00+00:00")]},
        "https://incois.gov.in",
        NOW,
    )
    r = await warnings.incois_alerts()
    assert r["data"]["count"] == 0


async def test_simulation_is_labelled(env: Path) -> None:
    from tarangyukti import sim_warning

    store = make_snapshot(env)
    sim_warning.apply(store, hours=24)
    r = await warnings.incois_alerts("Ramanathapuram")
    assert r["data"]["count"] == 2
    assert any(w["simulation"] for w in r["data"]["active"])
    assert any("SIMULATION" in n for n in r["notes"])
    sim_warning.apply(store, clear=True)
    assert store.verify() == []


async def test_imd_without_snapshot_is_unavailable() -> None:
    r = await warnings.imd_warnings("Ramanathapuram")
    assert r["data"]["available"] is False
    assert "SACHET down" in r["data"]["reason"]


async def test_pfz_from_snapshot(env: Path) -> None:
    make_snapshot(env)
    r = await warnings.pfz_incois("Tamil Nadu")
    assert r["data"]["zones"][0]["id"] == "Z1"
    assert r["confidence"] == "low"  # online path failed, snapshot fallback
    wrong = await warnings.pfz_incois("Kerala")
    assert wrong["data"]["available"] is False


async def test_pfz_expired_flagged(env: Path) -> None:
    make_snapshot(env)
    freeze(NOW + timedelta(days=3))
    r = await warnings.pfz_incois()
    assert any("expired" in n for n in r["notes"])


def test_snapshot_payload_is_json(env: Path) -> None:
    store = make_snapshot(env)
    for f in store.files():
        orjson.loads(f.read_bytes())
