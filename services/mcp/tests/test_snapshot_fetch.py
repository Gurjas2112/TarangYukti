from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from tarangyukti import fetch
from tarangyukti.snapshot import SnapshotStore

from .conftest import make_snapshot


def test_manifest_detects_tampering(env: Path) -> None:
    store = make_snapshot(env)
    assert store.verify() == []
    (store.dir / "sst.json").write_text('{"tampered": true}', encoding="utf-8")
    assert store.verify() == ["sst.json"]


def test_missing_manifest_reported(env: Path) -> None:
    store = SnapshotStore("2026-01-01", env / "snapshot")
    assert store.verify() == ["manifest.json"]


def test_bad_date_rejected() -> None:
    with pytest.raises(ValueError):
        SnapshotStore("../etc")


def test_allowlist() -> None:
    assert fetch.allowed("https://marine-api.open-meteo.com/v1/marine")
    assert fetch.allowed("https://coastwatch.noaa.gov/erddap/x.json")
    assert not fetch.allowed("https://evil.example.com/open-meteo.com")
    assert not fetch.allowed("https://open-meteo.com.evil.example/x")


async def test_not_allowed_domain_raises() -> None:
    with pytest.raises(fetch.NotAllowed):
        await fetch.get_json("https://example.com/data.json")


@respx.mock
async def test_redirect_outside_allowlist_blocked() -> None:
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(302, headers={"location": "https://example.com/x"})
    )
    respx.get("https://example.com/x").mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(fetch.NotAllowed):
        await fetch.get_json("https://api.open-meteo.com/v1/forecast")


@respx.mock
async def test_http_error_is_source_unavailable() -> None:
    respx.get("https://api.open-meteo.com/v1/forecast").mock(return_value=httpx.Response(500))
    with pytest.raises(fetch.SourceUnavailable):
        await fetch.get_json("https://api.open-meteo.com/v1/forecast")
