"""Push sender (Expo + web) and the alert budget (Milestone 6). Frozen clocks, no network."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr
from pywebpush import WebPushException
from ty_common.settings import get_settings

from ty_worker import budget, outbox, push

NOW = datetime(2026, 11, 4, 0, 0, tzinfo=UTC)  # 05:30 IST


class Conn:
    def __init__(self) -> None:
        self.sql: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, q: str, args: tuple[Any, ...] = ()) -> None:
        self.sql.append((q, args))


EXPO = {"id": "s1", "kind": "expo", "endpoint": "ExponentPushToken[abc]"}
WEB = {"id": "s2", "kind": "web", "endpoint": "https://push.example/x", "p256dh": "k", "auth": "a"}
MSG: push.Message = {"id": "a1", "kind": "brief", "title": "Morning brief", "body": "Good to go.", "url": "/brief"}


@respx.mock
async def test_expo_ok_updates_last_ok() -> None:
    route = respx.post(push.EXPO_PUSH_URL).mock(return_value=httpx.Response(200, json={"data": {"status": "ok"}}))
    c = Conn()
    assert await push.send(EXPO, MSG, urgent=True, conn=c) is True  # type: ignore[arg-type]
    body = route.calls[0].request.content.decode()
    assert '"priority":"high"' in body.replace(" ", "") and '"channelId":"danger"' in body.replace(" ", "")
    assert "last_ok_at" in c.sql[0][0]


@respx.mock
async def test_expo_device_gone_deletes_subscription() -> None:
    respx.post(push.EXPO_PUSH_URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"status": "error", "details": {"error": "DeviceNotRegistered"}}}
        )
    )
    c = Conn()
    assert await push.send(EXPO, MSG, urgent=False, conn=c) is False  # type: ignore[arg-type]
    assert c.sql[0][0].startswith("delete from push_subscriptions")


@respx.mock
async def test_expo_outage_is_retryable() -> None:
    respx.post(push.EXPO_PUSH_URL).mock(return_value=httpx.Response(503))
    c = Conn()
    assert await push.send(EXPO, MSG, urgent=False, conn=c) is False  # type: ignore[arg-type]
    assert c.sql == []  # kept for retry


@pytest.mark.parametrize(("status", "deleted"), [(410, True), (404, True), (500, False)])
async def test_web_push_status(monkeypatch: pytest.MonkeyPatch, status: int, deleted: bool) -> None:
    monkeypatch.setattr(get_settings(), "vapid_private_key", get_settings().vapid_private_key or SecretStr("x"))

    def fail(**kw: Any) -> None:
        raise WebPushException("gone", response=httpx.Response(status))  # type: ignore[arg-type]

    monkeypatch.setattr(push, "webpush", fail)
    c = Conn()
    assert await push.send(WEB, MSG, urgent=False, conn=c) is False  # type: ignore[arg-type]
    assert bool(c.sql and c.sql[0][0].startswith("delete")) is deleted


async def test_web_payload_has_no_coordinates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "vapid_private_key", get_settings().vapid_private_key or SecretStr("x"))
    seen: dict[str, Any] = {}
    monkeypatch.setattr(push, "webpush", lambda **kw: seen.update(kw))
    row = {"id": "a1", "kind": "brief", "title": "t", "body": "b", "url": "/brief?harbour=rameswaram&boat=small_frp"}
    assert await push.send(WEB, outbox.message(row), urgent=False, conn=Conn()) is True  # type: ignore[arg-type]
    assert set(__import__("json").loads(seen["data"])) == {"id", "kind", "title", "body", "url"}
    assert not __import__("re").search(r"\d+\.\d{3,}", seen["data"])


# ── budget


def test_critical_always_goes_even_in_quiet_hours() -> None:
    night = datetime(2026, 11, 3, 17, 0, tzinfo=UTC)  # 22:30 IST
    assert budget.decide(kind="alert", critical=True, now=night, sent_non_critical_today=9) == "send"


def test_non_critical_held_in_quiet_hours_and_capped() -> None:
    night = datetime(2026, 11, 3, 17, 0, tzinfo=UTC)
    assert budget.decide(kind="alert", critical=False, now=night) == "hold"
    day = datetime(2026, 11, 4, 6, 0, tzinfo=UTC)  # 11:30 IST
    assert budget.decide(kind="alert", critical=False, now=day, sent_non_critical_today=2) == "send"
    assert budget.decide(kind="alert", critical=False, now=day, sent_non_critical_today=3) == "suppress"


def test_same_rule_repeats_after_two_hours_only() -> None:
    day = datetime(2026, 11, 4, 6, 0, tzinfo=UTC)
    recent = day - timedelta(minutes=90)
    assert budget.decide(kind="alert", critical=True, now=day, last_same_rule_at=recent) == "suppress"
    assert budget.decide(kind="alert", critical=True, now=day, last_same_rule_at=day - timedelta(hours=2)) == "send"


def test_quiet_hours_custom_and_wrapping() -> None:
    assert budget.in_quiet_hours(NOW - timedelta(hours=3), time(21, 0), time(3, 30))  # 02:30 IST
    assert not budget.in_quiet_hours(NOW, time(21, 0), time(3, 30))  # 05:30 IST
    assert budget.in_quiet_hours(NOW, time(5, 0), time(6, 0))


def test_brief_is_due_30_min_before_learned_departure() -> None:
    deps = [time(5, 0), time(5, 30), time(4, 30), time(5, 10), time(5, 20)]
    due = budget.brief_due_at(NOW, None, deps)
    assert due.astimezone(budget.IST).strftime("%H:%M") == "04:40"  # median 05:10 minus 30 min
    assert budget.brief_due_at(NOW, None, []).astimezone(budget.IST).strftime("%H:%M") == "03:30"
    assert budget.brief_due_at(NOW, time(3, 0), deps).astimezone(budget.IST).strftime("%H:%M") == "03:00"


def test_briefs_and_tests_bypass_the_budget() -> None:
    night = datetime(2026, 11, 3, 22, 0, tzinfo=UTC)  # 03:30 IST
    assert budget.decide(kind="brief", critical=False, now=night, sent_non_critical_today=5) == "send"
    assert budget.decide(kind="test", critical=False, now=night) == "send"


def test_slot_stops_before_next_scheduled_start() -> None:
    # Job starts at 18:40:00 (slot 300 s); the image takes 75 s to pull.
    start = 1_793_904_000.0  # a multiple of 300
    assert outbox.seconds_left_in_slot(300, now=start + 75) == 300 - 20 - 75
    assert outbox.seconds_left_in_slot(300, now=start + 290) == 0.0
