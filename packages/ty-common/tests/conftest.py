from __future__ import annotations

from collections.abc import AsyncIterator

import fakeredis
import pytest
from fakeredis import FakeAsyncRedis

from ty_common.cache import Cache, set_cache


@pytest.fixture
def server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


@pytest.fixture
async def cache(server: fakeredis.FakeServer) -> AsyncIterator[Cache]:
    c = Cache(FakeAsyncRedis(server=server), disabled=False)
    set_cache(c)
    yield c
    await c.drain()
    await c.stop_listener()
    set_cache(None)


def other_process(server: fakeredis.FakeServer) -> Cache:
    """A second Cache on the same Redis stands in for another process with its own L1."""
    return Cache(FakeAsyncRedis(server=server), disabled=False)
