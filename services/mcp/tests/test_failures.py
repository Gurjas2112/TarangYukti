"""Replays every tools-layer row of tests/failures/failures.yaml (spec §6.4.4)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import h3
import pytest
import redis.asyncio as aioredis
import yaml
from ty_common.cache import Cache, cached, fingerprint

from tarangyukti.yukti import engine

from .yukti_helpers import T0, make_ctx

ROWS: list[dict[str, Any]] = yaml.safe_load(
    (Path(__file__).resolve().parents[3] / "tests" / "failures" / "failures.yaml").read_text(encoding="utf-8")
)


def _row(rid: str) -> dict[str, Any]:
    return next(r for r in ROWS if r["id"] == rid)


def test_every_tools_row_has_a_replay() -> None:
    assert {r["id"] for r in ROWS if r["layer"] == "tools"} <= set(REPLAYS)


def f001() -> None:
    inp = _row("F-001")["input"]
    start = h3.latlng_to_cell(*inp["start"], 7)
    goal = h3.latlng_to_cell(*inp["goal"], 7)
    ctx = make_ctx(inp["boat_type"])
    ev = engine.evaluate(ctx, engine.candidate(ctx, start, goal, T0))
    assert ev.candidate.route_found is _row("F-001")["expect"]["route_found"]


async def f002() -> None:
    n = _row("F-002")["input"]["concurrent_calls"]
    c = Cache(aioredis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2), disabled=False)

    @cached(ns="tool", ttl=60, key=lambda i: fingerprint("f002", i), cache=c)
    async def tool(i: int) -> dict[str, int]:
        return {"i": i}

    results = await asyncio.gather(*(tool(i % 3) for i in range(n)))
    assert (len(results) == n) is _row("F-002")["expect"]["all_answered"]


REPLAYS = {"F-001": f001, "F-002": f002}


@pytest.mark.parametrize("rid", sorted(REPLAYS))
async def test_failure_row(rid: str) -> None:
    out = REPLAYS[rid]()
    if asyncio.iscoroutine(out):
        await out
