from fastapi.testclient import TestClient

from ty_channels.app import app


def test_health() -> None:
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
