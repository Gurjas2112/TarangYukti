"""Channels API (Milestone 6): public endpoints, login checks, validation and rate limits. No network, no DB."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import fakeredis
import pytest
from fastapi.testclient import TestClient
from ty_common.cache import Cache, set_cache

from ty_channels import app as app_module
from ty_channels import public, voice

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def cache() -> Iterator[Cache]:
    c = Cache(fakeredis.FakeAsyncRedis(server=fakeredis.FakeServer()), disabled=False)
    set_cache(c)
    yield c
    set_cache(None)


def test_languages_and_harbours_are_public_and_cacheable() -> None:
    r = client.get("/languages", params={"locale": "ta"})
    assert r.status_code == 200 and "public" in r.headers["cache-control"]
    body = r.json()
    assert len(body["languages"]) == 23 and body["suggested"] == "ta-IN"
    h = client.get("/harbours").json()["harbours"]
    assert any(x["id"] == "rameswaram" and x["suggested_language"] == "ta-IN" for x in h)


def test_brief_validates_and_calls_the_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    async def fake(name: str, args: dict[str, Any]) -> dict[str, Any]:
        seen.update(name=name, args=args)
        return {"verdict": "GO", "headline": "Good to go."}

    monkeypatch.setattr(public, "call_tool", fake)
    r = client.get("/brief", params={"harbour": "rameswaram", "boat_type": "small_frp", "lang": "ta-IN"})
    assert r.status_code == 200 and r.json()["verdict"] == "GO"
    assert seen == {
        "name": "sea_brief",
        "args": {"harbour_id": "rameswaram", "boat_type": "small_frp", "lang": "ta-IN"},
    }
    assert client.get("/brief", params={"harbour": "x", "boat_type": "small_frp", "lang": "ta-IN"}).status_code == 422
    assert (
        client.get("/brief", params={"harbour": "rameswaram", "boat_type": "yacht", "lang": "ta-IN"}).status_code == 422
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/me"),
        ("post", "/onboarding"),
        ("put", "/me/prefs"),
        ("post", "/push/subscribe"),
        ("post", "/phone-link"),
    ],
)
def test_personal_routes_need_login(method: str, path: str) -> None:
    r = client.request(method.upper(), path, json={} if method != "get" else None)
    assert r.status_code == 401


def test_bad_token_is_401(monkeypatch: pytest.MonkeyPatch) -> None:
    r = client.get("/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_subscribe_and_prefs_validation() -> None:
    from ty_channels import me

    app_module.app.dependency_overrides[me.signed_in] = lambda: {"sub": "00000000-0000-0000-0000-000000000001"}
    try:
        r = client.post("/push/subscribe", json={"kind": "expo", "endpoint": "https://x"})
        assert r.status_code == 422
        r = client.post("/push/subscribe", json={"kind": "web", "endpoint": "https://push.example/x"})
        assert r.status_code == 422  # web needs p256dh + auth
        r = client.put("/me/prefs", json={"brief_time": "25:00"})
        assert r.status_code == 422
        r = client.put("/me/prefs", json={"language": "xx-IN"})
        assert r.status_code == 422
    finally:
        app_module.app.dependency_overrides.clear()


def test_tts_group_b_gets_text_only() -> None:
    r = client.post("/tts", json={"text": "hello", "lang": "ur-IN"})
    assert r.status_code == 200 and r.json()["url"] is None


def test_tts_uses_cache_and_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def synth(text: str, code: str) -> dict[str, str]:
        calls.append(text)
        return {"url": "https://example/x.mp3"}

    monkeypatch.setattr(voice, "synthesise", synth)
    for _ in range(20):
        assert client.post("/tts", json={"text": "Good to go.", "lang": "en-IN"}).status_code == 200
    r = client.post("/tts", json={"text": "Good to go.", "lang": "en-IN"})
    assert r.status_code == 429 and r.headers["retry-after"] == "3600"


def test_unknown_language_rejected() -> None:
    assert client.post("/tts", json={"text": "x", "lang": "xx-IN"}).status_code == 422


def test_consent_wording_has_a_version() -> None:
    r = client.get("/consent", params={"lang": "en-IN"})
    assert r.status_code == 200
    body = r.json()
    assert body["notice_version"] and body["short"] and body["agree"]
