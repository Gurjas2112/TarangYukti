"""FrontDoorOnly: direct requests are refused when FRONTDOOR_ID is set; health stays open (spec §16 Edge)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ty_common.edge import FrontDoorOnly


def make(fdid: str | None) -> TestClient:
    app = FastAPI()
    app.add_middleware(FrontDoorOnly, fdid=fdid)

    @app.get("/health")
    def health() -> str:
        return "ok"

    @app.get("/brief")
    def brief() -> str:
        return "card"

    return TestClient(app)


def test_direct_request_refused_front_door_passes() -> None:
    c = make("fd-123")
    assert c.get("/brief").status_code == 403
    assert c.get("/brief", headers={"X-Azure-FDID": "other"}).status_code == 403
    assert c.get("/brief", headers={"X-Azure-FDID": "fd-123"}).status_code == 200
    assert c.get("/health").status_code == 200


def test_no_front_door_configured_no_check() -> None:
    assert make("").get("/brief").status_code == 200
