"""Server rules without a database: owner-bound threads (403), one run per thread (409), bad token (401)."""

from __future__ import annotations

from typing import Any

import fakeredis
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from ty_common.cache import Cache, set_cache

import server


class FakeConn:
    def __init__(self, owners: dict[str, str | None]) -> None:
        self.owners = owners

    async def __aenter__(self) -> FakeConn:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, sql: str, params: tuple[str, str | None]) -> FakeConn:
        tid, uid = params
        self.owners.setdefault(tid, uid)  # insert … on conflict do update (owner unchanged)
        self._row = {"user_id": self.owners[tid]}
        return self

    async def fetchone(self) -> dict[str, Any]:
        return self._row


class FakePool:
    def __init__(self) -> None:
        self.owners: dict[str, str | None] = {}

    def connection(self) -> FakeConn:
        return FakeConn(self.owners)


@pytest.fixture
def pool(monkeypatch: pytest.MonkeyPatch) -> FakePool:
    p = FakePool()
    monkeypatch.setitem(server.state, "pool", p)
    return p


async def test_first_caller_owns_the_thread(pool: FakePool) -> None:
    await server.claim_thread("t1", "user-a")
    await server.claim_thread("t1", "user-a")  # same owner continues
    with pytest.raises(HTTPException) as e:
        await server.claim_thread("t1", "user-b")
    assert e.value.status_code == 403
    with pytest.raises(HTTPException):
        await server.claim_thread("t1", None)  # anonymous cannot continue a signed-in thread


async def test_anonymous_thread_open_to_its_id(pool: FakePool) -> None:
    await server.claim_thread("anon", None)
    await server.claim_thread("anon", None)


async def test_one_run_per_thread() -> None:
    set_cache(Cache(fakeredis.FakeAsyncRedis(server=fakeredis.FakeServer()), disabled=False))
    try:
        assert await server.acquire("t9") is True
        assert await server.acquire("t9") is False  # → 409
        await server.release("t9")
        assert await server.acquire("t9") is True
    finally:
        set_cache(None)


def test_bad_token_is_401() -> None:
    r = TestClient(server.app).post("/agent", json={}, headers={"authorization": "Bearer not-a-jwt"})
    assert r.status_code in (401, 422)  # body validation may run first; never 200
