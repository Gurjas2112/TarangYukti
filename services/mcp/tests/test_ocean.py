"""anomaly_series and pfz_compute (Milestone 7): fronts, zones, overlap and the heatwave test on synthetic data."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from tarangyukti import config
from tarangyukti.tools import ocean


def step_field(lat0: float = 9.0, lon0: float = 79.0, n: int = 12, step: float = 0.05) -> list[dict[str, float]]:
    """SST 28 °C west of lon0 + n/2·step, 29 °C east of it: one sharp north-south front."""
    edge = lon0 + (n // 2) * step
    return [
        {
            "lat": round(lat0 + i * step, 4),
            "lon": round(lon0 + j * step, 4),
            "value": 28.0 if lon0 + j * step < edge else 29.0,
        }
        for i in range(n)
        for j in range(n)
    ]


def test_sobel_finds_the_front_and_only_there() -> None:
    fronts, step = ocean.sst_fronts(step_field())
    assert step == 0.05
    strong = [f for f in fronts if f[2] >= 0.15]
    assert strong and {round(f[1], 2) for f in strong} <= {79.25, 79.3}  # the two columns either side of the edge
    calm = [f for f in fronts if f[1] < 79.2]
    assert all(f[2] == 0 for f in calm)


def test_masked_cells_are_never_interpolated() -> None:
    pts = [p for p in step_field() if not (p["lat"] == 9.25 and p["lon"] == 79.25)]
    fronts, _ = ocean.sst_fronts(pts)
    assert all(not (abs(f[0] - 9.25) <= 0.05 and abs(f[1] - 79.25) <= 0.05) for f in fronts)


def test_zones_need_high_chlorophyll_near_a_front() -> None:
    p = dict(config.constraints()["pfz_compute"])
    sst = step_field()
    near = [{"lat": 9.2 + k * 0.03, "lon": 79.28, "value": 2.5} for k in range(4)]
    low = [{"lat": 9.2 + k * 0.03, "lon": 79.29, "value": 0.2} for k in range(4)]
    far = [{"lat": 9.2 + k * 0.03, "lon": 78.3, "value": 3.0} for k in range(4)]
    zs, fronts = ocean.zones(sst, near + low + far, p)
    assert fronts and len(zs) == 1
    z = zs[0]
    assert z["points"] == 4 and z["mean_chl_mg_m3"] == 2.5
    assert z["geometry"]["type"] == "Polygon" and abs(z["centroid"]["lon"] - 79.28) < 0.02


def test_overlap_score() -> None:
    p = dict(config.constraints()["pfz_compute"])
    zs, _ = ocean.zones(step_field(), [{"lat": 9.2 + k * 0.03, "lon": 79.28, "value": 2.5} for k in range(4)], p)
    incois = [{"lat": 9.25, "lon": 79.28}, {"lat": 8.5, "lon": 78.5}]
    assert ocean.overlap(zs, incois) == 0.5
    assert ocean.overlap(zs, []) is None


def series(anoms: list[float | None]) -> list[dict[str, Any]]:
    return [{"date": f"2026-10-{i + 1:02d}", "sst_c": 29.0, "anom_c": a} for i, a in enumerate(anoms)]


def test_heatwave_test_uses_config_thresholds() -> None:
    hot = ocean.heatwave(series([1.5] * 10))
    assert hot["tested"] and hot["heatwave"] and hot["days_above"] == 10
    assert not ocean.heatwave(series([0.2] * 10))["heatwave"]
    assert ocean.heatwave(series([2.0, None, None]))["tested"] is False


@respx.mock
async def test_anomaly_series_parses_erddap() -> None:
    payload = {
        "table": {
            "columnNames": ["time", "zlev", "latitude", "longitude", "anom", "sst"],
            "rows": [[f"2026-10-{d:02d}T12:00:00Z", 0, 9.125, 79.375, 1.2, 29.5] for d in range(1, 31)],
        }
    }
    respx.get(url__startswith="https://coastwatch.pfeg.noaa.gov/").mock(return_value=httpx.Response(200, json=payload))
    r = await ocean.anomaly_series(9.2, 79.4, 30)
    assert r["data"]["point"] == {"lat": 9.125, "lon": 79.375}
    assert r["data"]["days"] == 30 and r["data"]["heatwave"]["heatwave"] is True
    assert r["source"].startswith("NOAA OISST")


async def test_anomaly_rejects_points_outside_the_region() -> None:
    from tarangyukti import qc

    with pytest.raises(qc.OutOfRegion):
        await ocean.anomaly_series(15.0, 79.0)
