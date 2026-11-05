"""The capture endpoint never exists outside a laptop with CAPTURE_SCENARIOS=1 (spec §17.14.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from ty_common import capture
from ty_common.settings import get_settings

from ty_channels.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _enable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(get_settings(), "env", "local")
    monkeypatch.setattr(get_settings(), "capture_scenarios", True)
    monkeypatch.setattr(get_settings(), "capture_token", SecretStr("t0k3n"))
    capture._cache = (0.0, -1.0, "normal")


@pytest.mark.parametrize("env", ["live", "preview", "ci"])
def test_404_outside_local(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env: str) -> None:
    _enable(monkeypatch, tmp_path)
    monkeypatch.setattr(get_settings(), "env", env)
    r = client.post("/admin/capture/scenario", json={"name": "normal"}, headers={"X-Capture-Token": "t0k3n"})
    assert r.status_code == 404


def test_token_required_and_scenarios_apply(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _enable(monkeypatch, tmp_path)
    assert client.post("/admin/capture/scenario", json={"name": "normal"}).status_code == 403
    h = {"X-Capture-Token": "t0k3n"}
    assert client.post("/admin/capture/scenario", json={"name": "nope"}, headers=h).status_code == 422

    assert client.post("/admin/capture/scenario", json={"name": "update-required"}, headers=h).status_code == 200
    assert client.get("/app/version").json()["minVersionCode"] == 1_000_000

    assert client.post("/admin/capture/scenario", json={"name": "fault-next-request"}, headers=h).status_code == 200
    assert client.get("/app/version").status_code == 500  # exactly one failure
    assert client.get("/app/version").status_code == 200
    assert capture.current() == "normal"
