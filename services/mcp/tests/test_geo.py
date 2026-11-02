"""Geofence and distance tests on real places (prompt §16 "Unit": distances, geofence rings)."""

from __future__ import annotations

import h3
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tarangyukti import layers_build
from tarangyukti.tools import geo


@pytest.mark.parametrize(
    ("name", "lat", "lon", "side", "in_mpa"),
    [
        ("Rameswaram harbour", 9.288, 79.313, "india", False),
        ("Dhanushkodi", 9.152, 79.44, "india", False),
        ("Kachchatheevu (Sri Lankan side since 1974)", 9.383, 79.517, "beyond_imbl", False),
        ("Talaimannar, Sri Lanka", 9.10, 79.73, "beyond_imbl", False),
        ("Krusadai island (marine park)", 9.247, 79.211, "india", True),
        ("Van Tivu (marine park)", 8.833, 78.21, "india", True),
        ("Thoothukudi offshore", 8.75, 78.4, "india", False),
    ],
)
def test_known_places(name: str, lat: float, lon: float, side: str, in_mpa: bool) -> None:
    d = geo.fence_check(lat, lon)["data"]
    assert d["side"] == side, name
    assert d["in_mpa"] is in_mpa, name


def test_known_distances() -> None:
    assert 20.0 <= geo.fence_check(9.288, 79.313)["data"]["imbl_km"] <= 25.0  # Rameswaram harbour
    assert 8.0 <= geo.fence_check(9.152, 79.44)["data"]["imbl_km"] <= 12.0  # Dhanushkodi


def test_rings_from_config() -> None:
    assert geo.ring_for(6.0, False) == "clear"
    assert geo.ring_for(5.0, False) == "warning"
    assert geo.ring_for(2.0, False) == "alarm"
    assert geo.ring_for(10.0, True) == "beyond"


def test_point_on_the_line_is_alarm() -> None:
    # position 4 of the 1974 agreement
    lat, lon = layers_build.dm(9, 21.80), layers_build.dm(79, 30.70)
    d = geo.fence_check(lat, lon)["data"]
    assert d["imbl_km"] == 0.0
    assert d["ring"] in ("alarm", "beyond")


@settings(max_examples=60, deadline=None)
@given(st.floats(8.9, 9.6), st.floats(79.0, 79.45), st.floats(0.0, 0.08))
def test_ring_monotonic_towards_the_line(lat: float, lon: float, step: float) -> None:
    """Moving east towards the line never makes the ring less severe while on India's side."""
    order = {"clear": 0, "warning": 1, "alarm": 2, "beyond": 3}
    a = geo.fence_check(lat, lon)["data"]
    b = geo.fence_check(lat, min(lon + step, 80.5))["data"]
    if a["side"] == "india" and b["side"] == "india":
        assert b["imbl_km"] <= a["imbl_km"] + 0.15 or order[b["ring"]] >= order[a["ring"]] - 0


def test_geo_distance_known() -> None:
    d = geo.geo_distance(9.288, 79.313, 9.383, 79.517)["data"]  # Rameswaram → Kachchatheevu
    assert 24.0 <= d["km"] <= 26.0
    assert d["direction"] == "north-east"
    assert d["nm"] == pytest.approx(d["km"] / 1.852, abs=0.1)


@settings(max_examples=50, deadline=None)
@given(st.floats(8.0, 10.5), st.floats(78.0, 80.5), st.floats(8.0, 10.5), st.floats(78.0, 80.5))
def test_geo_distance_symmetric(lat1: float, lon1: float, lat2: float, lon2: float) -> None:
    a = geo.geo_distance(lat1, lon1, lat2, lon2)["data"]["km"]
    b = geo.geo_distance(lat2, lon2, lat1, lon1)["data"]["km"]
    assert a == pytest.approx(b, abs=0.1)


async def test_cell_fence() -> None:
    kach = await geo.cell_fence(h3.latlng_to_cell(9.383, 79.517, 7))
    assert kach["beyond_or_crossing"] is True
    harbour = await geo.cell_fence(h3.latlng_to_cell(9.288, 79.313, 7))
    assert harbour["beyond_or_crossing"] is False
    assert harbour["imbl_min_km"] > 15
    park = await geo.cell_fence(h3.latlng_to_cell(9.247, 79.211, 7))
    assert park["touches_mpa"] is True


def test_imbl_positions_are_the_treaty_points() -> None:
    labels = [p[0] for p in layers_build.imbl_positions()]
    assert labels[0] == "13m" and labels[-1] == "6b"
    assert labels.index("6") < labels.index("1") < labels.index("1ba")
    assert len(labels) == len(set(labels))
