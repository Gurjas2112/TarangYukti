"""Postgres access for request handlers: every query runs as `authenticated` with the caller's JWT claims, so
RLS decides what a user sees (spec §8.4, §9.1). Services connect as `ty_api` (no BYPASSRLS).

    async with user_tx(claims) as cur:
        await cur.execute("select * from boats")
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import orjson
from psycopg import AsyncCursor
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from .settings import get_settings

_pool: AsyncConnectionPool | None = None


def pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        url = get_settings().database_url
        if url is None:
            raise RuntimeError("DATABASE_URL is not set (run make db-roles)")
        _pool = AsyncConnectionPool(
            url.get_secret_value(),
            min_size=0,
            max_size=10,
            open=False,
            kwargs={"prepare_threshold": None, "row_factory": dict_row},
        )
    return _pool


async def open_pool() -> None:
    await pool().open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def user_tx(claims: dict[str, Any]) -> AsyncIterator[AsyncCursor[DictRow]]:
    """One transaction as the signed-in user: request.jwt.claims + role authenticated (both transaction-local)."""
    async with pool().connection() as conn, conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("select set_config('request.jwt.claims', %s, true)", (orjson.dumps(claims).decode(),))
        await cur.execute("set local role authenticated")
        yield cur


@asynccontextmanager
async def anon_tx() -> AsyncIterator[AsyncCursor[DictRow]]:
    """One transaction as `anon`: public reads (documents, citations) under the same RLS as the Data API."""
    async with pool().connection() as conn, conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("set local role anon")
        yield cur
