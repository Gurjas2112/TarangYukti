"""Trip and border-alert rules (Milestone 8) with fixed times."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ty_common import trips
from ty_common.phrases import harbour

T = datetime(2026, 11, 4, 0, 0, tzinfo=UTC)  # 05:30 IST


def test_harbour_circle_uses_config_radius() -> None:
    h = harbour("rameswaram")
    assert trips.geofence_m() == 1500
    assert trips.at_harbour(h["lat"], h["lon"], h)
    assert trips.at_harbour(h["lat"] + 0.012, h["lon"], h)  # ~1.3 km north
    assert not trips.at_harbour(h["lat"] + 0.02, h["lon"], h)  # ~2.2 km north


def test_transitions() -> None:
    assert trips.transition(trip_open=False, inside_harbour=False) == "open"
    assert trips.transition(trip_open=True, inside_harbour=True) == "close"
    assert trips.transition(trip_open=True, inside_harbour=False) is None
    assert trips.transition(trip_open=False, inside_harbour=True) is None


def test_rings_come_from_config() -> None:
    assert trips.alert_rings_km() == {"warning": 5.0, "alarm": 2.0}
    assert trips.fence_rules(6.0, beyond=False, in_mpa=False) == []
    assert trips.fence_rules(4.9, beyond=False, in_mpa=False) == ["border-5km"]
    assert trips.fence_rules(1.8, beyond=False, in_mpa=True) == ["border-2km", "mpa"]
    assert trips.fence_rules(0.3, beyond=True, in_mpa=False) == ["beyond-imbl"]


def test_same_rule_once_per_two_hours() -> None:
    sent = [trips.Sent("border-5km", T)]
    assert not trips.should_alert("border-5km", T + timedelta(minutes=90), sent)
    assert trips.should_alert("border-5km", T + timedelta(hours=2), sent)


def test_a_rising_level_always_alerts_a_falling_one_does_not() -> None:
    assert trips.should_alert("border-2km", T + timedelta(minutes=5), [trips.Sent("border-5km", T)])
    assert trips.should_alert("beyond-imbl", T + timedelta(minutes=5), [trips.Sent("border-2km", T)])
    assert not trips.should_alert("border-5km", T + timedelta(minutes=5), [trips.Sent("border-2km", T)])
    assert trips.should_alert("mpa", T + timedelta(minutes=5), [trips.Sent("border-2km", T)])


def test_right_on_counts_answered_trips_only() -> None:
    assert trips.right_on(["right", None, "wrong", "right"]) == (2, 3)
    assert trips.right_on([]) == (0, 0)
    assert trips.right_on(["right"] * 40) == (30, 30)
