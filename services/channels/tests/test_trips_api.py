"""Positions, trips and sharing (Milestone 8): login, validation and timestamps. No DB, no network."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ty_channels import app as app_module
from ty_channels import me
from ty_channels.trips import Fix, check_times

client = TestClient(app_module.app)
BOAT = "35fa9392-090b-48be-a58a-1dfd42144006"
NOW = datetime(2026, 11, 4, 6, 0, tzinfo=UTC)


@pytest.fixture
def signed_in() -> Iterator[None]:
    app_module.app.dependency_overrides[me.signed_in] = lambda: {"sub": "00000000-0000-0000-0000-000000000001"}
    yield
    app_module.app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/positions"), ("get", "/trips"), ("post", "/trips/back"), ("post", "/share"), ("get", "/family")],
)
def test_login_required(method: str, path: str) -> None:
    assert client.request(method.upper(), path, json={} if method == "post" else None).status_code == 401


def fix(minutes_ago: float, lat: float = 9.3) -> Fix:
    return Fix(lat=lat, lon=79.36, recorded_at=NOW - timedelta(minutes=minutes_ago))


def test_future_fix_rejected_and_old_fixes_dropped() -> None:
    with pytest.raises(HTTPException):
        check_times([fix(-10)], NOW)
    kept = check_times([fix(3), fix(60 * 30), fix(1), fix(-1)], NOW)  # one in the 2-minute slack
    assert [round((NOW - f.recorded_at).total_seconds() / 60) for f in kept] == [3, 1, -1]
    with pytest.raises(HTTPException):
        check_times([fix(60 * 25)], NOW)


def test_fix_needs_a_timezone_and_the_region() -> None:
    with pytest.raises(ValueError):
        Fix(lat=9.3, lon=79.3, recorded_at=datetime(2026, 11, 4, 6, 0))
    with pytest.raises(ValueError):
        Fix(lat=12.0, lon=79.3, recorded_at=NOW)


def test_positions_body_validated_before_any_storage(signed_in: None) -> None:
    body = {
        "boat_id": BOAT,
        "source": "web_live",
        "fixes": [{"lat": 12.0, "lon": 79.3, "recorded_at": NOW.isoformat()}],
    }
    assert client.post("/positions", json=body).status_code == 422
    body = {
        "boat_id": BOAT,
        "source": "satellite",
        "fixes": [{"lat": 9.3, "lon": 79.3, "recorded_at": NOW.isoformat()}],
    }
    assert client.post("/positions", json=body).status_code == 422
    body = {"boat_id": BOAT, "source": "web_live", "fixes": []}
    assert client.post("/positions", json=body).status_code == 422
    many = [{"lat": 9.3, "lon": 79.3, "recorded_at": NOW.isoformat()}] * 101
    assert client.post("/positions", json={"boat_id": BOAT, "source": "web_live", "fixes": many}).status_code == 422


def test_share_validation(signed_in: None) -> None:
    assert client.post("/share", json={"boat_id": BOAT, "email": "not-an-email", "days": 30}).status_code == 422
    assert client.post("/share", json={"boat_id": BOAT, "email": "a@b.in", "days": 91}).status_code == 422
    assert client.post(f"/trips/{BOAT}/feedback", json={"feedback": "maybe"}).status_code == 422
    assert client.post(f"/trips/{BOAT}/feedback", json={"feedback": "right", "note": "x" * 501}).status_code == 422
