from __future__ import annotations

from pathlib import Path

import pytest

from ty_common import capture
from ty_common.settings import get_settings


@pytest.fixture
def local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("TY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(get_settings(), "env", "local")
    monkeypatch.setattr(get_settings(), "capture_scenarios", True)
    capture._cache = (0.0, -1.0, "normal")
    return tmp_path


def test_disabled_outside_local_capture(monkeypatch: pytest.MonkeyPatch, local: Path) -> None:
    capture.set_scenario("llm-offline")
    assert capture.current() == "llm-offline"
    monkeypatch.setattr(get_settings(), "env", "live")  # Tier 1: never a scenario, whatever the file says
    capture._cache = (0.0, -1.0, "normal")
    assert capture.current() == "normal"
    with pytest.raises(PermissionError):
        capture.set_scenario("normal")


def test_unknown_names_rejected_and_normal_resets(local: Path) -> None:
    with pytest.raises(ValueError):
        capture.set_scenario("delete-everything")
    capture.set_scenario("stale-data")
    assert capture.active("stale-data")
    capture.set_scenario("normal")
    assert capture.current() == "normal"
