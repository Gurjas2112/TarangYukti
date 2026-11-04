"""Expert and analyst endpoints (Milestone 7). MCP calls are faked; no network, no DB."""

from __future__ import annotations

from typing import Any

import h3
import pytest
from fastapi.testclient import TestClient

from ty_channels import app as app_module
from ty_channels import expert

client = TestClient(app_module.app)


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []
    route = [h3.latlng_to_cell(9.29, 79.31, 7), h3.latlng_to_cell(9.4, 79.3, 7), h3.latlng_to_cell(9.55, 79.3, 7)]

    async def fake(name: str, args: dict[str, Any]) -> dict[str, Any]:
        calls.append((name, args))
        if name == "yukti_evaluate":
            ev = {
                "outcome": "GO",
                "ledger": [{"id": "H1", "ok": True}],
                "route_cells": route if "goal_lat" in args else [],
            }
            return {"data": {"verdict": "GO", "requested": ev, "earliest_window": dict(ev), "recommended": None}}
        if name in ("sst_grid", "chl_grid"):
            return {
                "source": "test grid",
                "data": {"time": "2026-11-02T12:00:00Z", "points": [{"lat": 9.0, "lon": 79.0, "value": 29.1}]},
            }
        return {"data": {"name": name}}

    monkeypatch.setattr(expert, "call_tool", fake)
    return calls


def test_plan_adds_route_geojson_and_harbour(tools: list[tuple[str, dict[str, Any]]]) -> None:
    r = client.get(
        "/expert/plan", params={"harbour": "rameswaram", "boat_type": "small_frp", "goal_lat": 9.55, "goal_lon": 79.3}
    )
    assert r.status_code == 200 and "public" in r.headers["cache-control"]
    d = r.json()["data"]
    assert d["harbour"]["id"] == "rameswaram"
    assert d["limits"]["H2"] == {"value": 5, "unit": "km", "op": ">="} and d["limits"]["H5"]["value"] == 1.5
    assert d["requested"]["route"]["type"] == "LineString" and len(d["requested"]["route"]["coordinates"]) == 3
    name, args = tools[0]
    assert name == "yukti_evaluate" and args["lat"] == 9.288 and args["goal_lat"] == 9.55


def test_plan_validation(tools: list[tuple[str, dict[str, Any]]]) -> None:
    base = {"harbour": "rameswaram", "boat_type": "small_frp"}
    assert client.get("/expert/plan", params={**base, "goal_lat": 9.5}).status_code == 422
    assert client.get("/expert/plan", params={**base, "depart_at": "2026-11-04T05:00:00"}).status_code == 422
    ok = client.get("/expert/plan", params={**base, "depart_at": "2026-11-04T05:00:00+05:30"})
    assert ok.status_code == 200 and tools[-1][1]["depart_at"] == "2026-11-04T05:00:00+05:30"
    assert client.get("/expert/plan", params={**base, "harbour": "atlantis"}).status_code == 422


def test_layers_are_served_and_unknown_is_404() -> None:
    r = client.get("/layers/imbl")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/geo+json")
    assert r.json()["type"] in ("FeatureCollection", "Feature")
    assert client.get("/layers/secret").status_code == 404


def test_csv_download(tools: list[tuple[str, dict[str, Any]]]) -> None:
    r = client.get("/grids/sst/csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "lat,lon,sst_c,time_utc,source" and lines[1].startswith("9.0,79.0,29.1,")


def test_netcdf_link_points_at_the_source() -> None:
    r = client.get("/grids/sst/netcdf").json()
    assert r["url"].startswith("https://coastwatch.pfeg.noaa.gov/erddap/griddap/") and ".nc?" in r["url"]
    assert "(8.0)" in r["url"] and "(80.5)" in r["url"]


def test_route_geojson_needs_two_cells() -> None:
    assert expert.route_geojson([]) is None
    c = h3.latlng_to_cell(9.3, 79.3, 7)
    assert expert.route_geojson([c]) is None
