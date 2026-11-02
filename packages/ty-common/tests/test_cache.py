from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import fakeredis
import orjson
import pytest
from hypothesis import given
from hypothesis import strategies as st

from ty_common import cache as cache_mod
from ty_common.cache import (
    Cache,
    cached,
    compute_config_version,
    fingerprint,
    norm_hour,
    norm_text,
    norm_window30,
    to_cell,
)

from .conftest import other_process

Tool = Callable[[str, str], Awaitable[dict[str, object]]]


class Upstream:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
        self.delay = 0.0

    async def fetch(self, cell: str, version: str) -> dict[str, object]:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("upstream down")
        return {"cell": cell, "wave_m": 1.2, "version": version, "cache": "miss"}


def key_of(cell: str, version: str) -> str:
    return "tool:v1:" + fingerprint("marine_forecast", cell, version)


def make_tool(up: Upstream, c: Cache, ttl: int = 3600) -> Tool:
    @cached(
        ns="tool",
        ttl=ttl,
        key=lambda cell, version: fingerprint("marine_forecast", cell, version),
        tags=lambda cell, version: [f"cell:{cell}"],
        cache=c,
    )
    async def marine_forecast(cell: str, version: str) -> dict[str, object]:
        return await up.fetch(cell, version)

    return marine_forecast


async def test_l1_then_l2_hit(cache: Cache, server: fakeredis.FakeServer) -> None:
    up = Upstream()
    tool = make_tool(up, cache)
    a = await tool("8761", "openmeteo@03Z")
    b = await tool("8761", "openmeteo@03Z")
    assert a == b and up.calls == 1
    # another process: its L1 is empty, it hits L2 and fills its own L1
    other = other_process(server)
    assert await make_tool(up, other)("8761", "openmeteo@03Z") == a
    assert up.calls == 1
    assert len(other.l1) == 1


async def test_new_source_version_gives_new_key(cache: Cache) -> None:
    up = Upstream()
    tool = make_tool(up, cache)
    await tool("8761", "openmeteo@03Z")
    await tool("8761", "openmeteo@09Z")
    assert up.calls == 2


def test_config_change_changes_version(tmp_path: Path) -> None:
    (tmp_path / "phrases").mkdir()
    (tmp_path / "constraints.yaml").write_text("H2: {imbl_min_km: 5}\n")
    (tmp_path / "boats.yaml").write_text("small_frp: {max_wave_m: 1.5}\n")
    (tmp_path / "phrases" / "en.yaml").write_text("footer: Advisory only\n")
    v1 = compute_config_version(tmp_path)
    (tmp_path / "boats.yaml").write_text("small_frp: {max_wave_m: 1.4}\n")
    v2 = compute_config_version(tmp_path)
    (tmp_path / "phrases" / "en.yaml").write_text("footer: Advisory only.\n")
    v3 = compute_config_version(tmp_path)
    assert len({v1, v2, v3}) == 3
    assert fingerprint("yukti", v1, "cell") != fingerprint("yukti", v2, "cell")


def test_repo_config_version_is_computable() -> None:
    assert len(cache_mod.config_version()) == 64


async def test_stampede_200_concurrent_one_computation(cache: Cache) -> None:
    up = Upstream()
    up.delay = 0.2
    tool = make_tool(up, cache)
    results = await asyncio.gather(*[tool("8761", "v1") for _ in range(200)])
    assert up.calls == 1
    assert all(r == results[0] for r in results)


async def test_stale_if_error(cache: Cache) -> None:
    up = Upstream()
    tool = make_tool(up, cache)
    await tool("8761", "v1")
    # the fresh copy expires everywhere; lastgood stays
    await cache.redis.delete(key_of("8761", "v1"))
    cache.l1.clear()
    up.fail = True
    got = await tool("8761", "v1")
    assert got["cache"] == "stale"
    assert got["wave_m"] == 1.2


async def test_error_without_lastgood_raises_and_releases_lock(cache: Cache) -> None:
    up = Upstream()
    up.fail = True
    tool = make_tool(up, cache)
    with pytest.raises(RuntimeError):
        await tool("8761", "v1")
    assert await cache.redis.get("lock:" + key_of("8761", "v1")) is None
    up.fail = False
    assert (await tool("8761", "v1"))["wave_m"] == 1.2


async def test_tag_invalidation_clears_l1_in_other_process(
    cache: Cache, server: fakeredis.FakeServer
) -> None:
    up = Upstream()
    other = other_process(server)
    await other.start_listener()
    try:
        tool_a, tool_b = make_tool(up, cache), make_tool(up, other)
        await tool_a("8761", "v1")
        await tool_b("8761", "v1")
        assert len(other.l1) == 1
        assert await cache.invalidate(tag="cell:8761") >= 1
        for _ in range(60):
            if len(other.l1) == 0:
                break
            await asyncio.sleep(0.05)
        assert len(other.l1) == 0
        assert len(cache.l1) == 0
        await tool_b("8761", "v1")
        assert up.calls == 2  # recomputed after invalidation
    finally:
        await other.stop_listener()


async def test_cache_disabled_writes_nothing(server: fakeredis.FakeServer) -> None:
    c = Cache(fakeredis.FakeAsyncRedis(server=server), disabled=True)
    up = Upstream()
    tool = make_tool(up, c)
    a = await tool("8761", "v1")
    b = await tool("8761", "v1")
    assert a == b and up.calls == 2
    assert await c.redis.dbsize() == 0


async def test_redis_down_bypasses_cache() -> None:
    import redis.asyncio as aioredis

    # nothing listens on port 1: ping fails fast, calls go straight to the source
    c = Cache(aioredis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2), disabled=False)
    up = Upstream()
    tool = make_tool(up, c)
    assert (await tool("8761", "v1"))["wave_m"] == 1.2
    assert (await tool("8761", "v1"))["wave_m"] == 1.2
    assert up.calls == 2


async def test_large_values_skip_l1(cache: Cache) -> None:
    @cached(ns="kb", ttl=600, key=lambda q: fingerprint(q), cache=cache)
    async def big(q: str) -> dict[str, str]:
        return {"blob": "x" * 70_000}

    await big("q")
    assert len(cache.l1) == 0
    assert await cache.redis.dbsize() >= 1


async def test_early_refresh(cache: Cache, monkeypatch: pytest.MonkeyPatch) -> None:
    up = Upstream()
    tool = make_tool(up, cache, ttl=100)
    await tool("8761", "v1")
    real = cache_mod.time.time
    monkeypatch.setattr(cache_mod.time, "time", lambda: real() + 85)  # past 80 % of the TTL
    cache.l1.clear()
    await tool("8761", "v1")  # served from L2; one background refresh scheduled
    await cache.drain()
    assert up.calls == 2


async def test_values_are_json_not_pickle(cache: Cache) -> None:
    await make_tool(Upstream(), cache)("8761", "v1")
    raw = await cache.redis.get(key_of("8761", "v1"))
    assert raw is not None
    assert orjson.loads(raw)["v"]["wave_m"] == 1.2


def test_normalisers() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    t = datetime(2026, 11, 2, 4, 45, tzinfo=ist)
    assert norm_hour(t) == "2026-11-01T23Z"
    assert norm_window30(t) == "2026-11-01T23:00Z"
    assert norm_window30(datetime(2026, 11, 2, 5, 31, tzinfo=UTC)) == "2026-11-02T05:30Z"
    assert norm_text("  Rameswaram\u00a0 harbour ") == "Rameswaram harbour"
    assert norm_text("Seer FISH", lower=True) == "seer fish"
    with pytest.raises(ValueError):
        norm_hour(datetime(2026, 11, 2, 4, 0))


def test_rameswaram_cell_is_res7() -> None:
    import h3

    assert h3.get_resolution(to_cell(9.288, 79.313)) == 7


@given(st.lists(st.integers(min_value=-(2**63), max_value=2**63 - 1) | st.text(), max_size=5))
def test_fingerprint_is_stable(parts: list[object]) -> None:
    assert fingerprint(*parts) == fingerprint(*parts)
    assert len(fingerprint(*parts)) == 64
