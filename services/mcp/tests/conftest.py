from __future__ import annotations

import shutil
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import fakeredis
import pytest
from ty_common.cache import Cache, set_cache
from ty_common.settings import get_settings

from tarangyukti.snapshot import SnapshotStore
from tarangyukti.tools import common

REPO = Path(__file__).resolve().parents[3]
DATE = "2026-11-02"
NOW = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)  # 08:30 IST


@pytest.fixture(autouse=True)
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    shutil.copytree(REPO / "data" / "layers", tmp_path / "layers")
    monkeypatch.setenv("TY_DATA_DIR", str(tmp_path))
    s = get_settings()
    monkeypatch.setattr(s, "data_mode", "online")
    monkeypatch.setattr(s, "snapshot_date", DATE)
    monkeypatch.setattr(s, "supabase_service_role_key", None)  # never reach real Storage from tests
    monkeypatch.setattr(s, "neo4j_password", None)  # never write the real ledger from tests
    common.freeze(NOW)
    yield tmp_path
    common.freeze(None)


@pytest.fixture(autouse=True)
def sachet_offline(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Live CAP alerts are stubbed as unavailable unless a test asks for `real_cap` (then use respx)."""
    if "real_cap" in request.fixturenames:
        return
    from tarangyukti.fetch import SourceUnavailable
    from tarangyukti.tools import cap

    async def down(issuer: str) -> tuple[list[object], list[str]]:
        raise SourceUnavailable("SACHET down (test)")

    monkeypatch.setattr(cap, "regional_warnings", down)


@pytest.fixture
def real_cap() -> None:
    """Marker fixture: keep the real CAP reader (mock HTTP with respx)."""


@pytest.fixture(autouse=True)
async def cache() -> AsyncIterator[Cache]:
    c = Cache(fakeredis.FakeAsyncRedis(server=fakeredis.FakeServer()), disabled=False)
    set_cache(c)
    yield c
    await c.drain()
    set_cache(None)


def hourly(start: datetime, n: int, **series: list[Any]) -> dict[str, Any]:
    return {
        "time": [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(n)],
        **series,
    }


def marine_payload(lat: float, lon: float, waves: list[float | None], start: datetime = NOW) -> dict[str, Any]:
    n = len(waves)
    return {
        "latitude": lat,
        "longitude": lon,
        "hourly": hourly(
            start,
            n,
            wave_height=waves,
            wave_direction=[185] * n,
            wave_period=[9.0] * n,
            swell_wave_height=[0.4] * n,
            ocean_current_velocity=[0.6] * n,
            ocean_current_direction=[214] * n,
            sea_surface_temperature=[30.1] * n,
        ),
    }


def wind_payload(lat: float, lon: float, n: int, speed: float = 14.0, start: datetime = NOW) -> dict[str, Any]:
    return {
        "latitude": lat,
        "longitude": lon,
        "hourly": hourly(
            start, n, wind_speed_10m=[speed] * n, wind_gusts_10m=[speed + 6] * n, wind_direction_10m=[230] * n
        ),
    }


def erddap(var: str, rows: list[tuple[float, float, float | None]], when: str = "2026-11-01T12:00:00Z") -> dict:
    return {
        "table": {
            "columnNames": ["time", "zlev", "latitude", "longitude", var],
            "rows": [[when, 0, la, lo, v] for la, lo, v in rows],
        }
    }


def warning(**kw: Any) -> dict[str, Any]:
    w = {
        "id": "INCOIS-HW-1",
        "issuer": "INCOIS",
        "kind": "high_wave",
        "title": "High wave alert",
        "sectors": ["Ramanathapuram"],
        "valid_from": "2026-11-02T00:00:00+00:00",
        "valid_to": "2026-11-02T12:00:00+00:00",
        "issued_at": "2026-11-01T18:00:00+00:00",
        "severity": "alert",
        "source_url": "https://incois.gov.in/site/services/osf.jsp",
    }
    return w | kw


def make_snapshot(root: Path, fetched_at: datetime = NOW - timedelta(hours=1)) -> SnapshotStore:
    store = SnapshotStore(DATE, root / "snapshot")
    store.write(
        "marine",
        [marine_payload(9.25, 79.5, [0.6] * 24), marine_payload(9.25, 79.25, [None] * 24)],  # 2nd is land
        "https://marine-api.open-meteo.com/v1/marine",
        fetched_at,
    )
    store.write(
        "wind", [wind_payload(9.25, 79.5, 24), wind_payload(9.25, 79.25, 24)], "https://api.open-meteo.com", fetched_at
    )
    store.write("sst", erddap("sst", [(9.125, 79.125, 29.8), (9.375, 79.375, None)]), "https://x.noaa.gov", fetched_at)
    store.write(
        "chl", erddap("chlor_a", [(9.1, 79.1, 1.2), (9.2, 79.2, -3.0)]), "https://coastwatch.noaa.gov", fetched_at
    )
    store.write("warnings_incois", {"warnings": [warning()]}, "https://incois.gov.in", fetched_at)
    store.write(
        "pfz_incois",
        {
            "issued_at": "2026-11-01T10:00:00+00:00",
            "valid_to": "2026-11-03T10:00:00+00:00",
            "sector": "Tamil Nadu",
            "zones": [{"id": "Z1", "lat": 9.0, "lon": 79.1, "text": "PFZ off Rameswaram"}],
        },
        "https://incois.gov.in/MarineFisheries/PfzAdvisory",
        fetched_at,
    )
    store.write_manifest()
    return store
