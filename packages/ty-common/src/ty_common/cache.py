"""The one two-tier cache for every TarangYukti service (prompt §7a, spec §6.7).

L1 is an in-process cachetools TLRU cache; L2 is Redis (redis.asyncio); values are JSON via orjson.
Never pickle. Keys are content-addressed: ``{ns}:v{schema}:{fingerprint}``.

Usage::

    @cached(ns="tool", ttl=3600, key=lambda cell, hour: fingerprint("marine_forecast", cell, hour, src_ver))
    async def marine_forecast(cell: str, hour: str) -> dict[str, object]: ...
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import time
import unicodedata
from collections.abc import Awaitable, Callable, Iterable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

import orjson
import redis.asyncio as aioredis
from cachetools import TLRUCache
from redis.exceptions import RedisError

from .settings import find_config_dir, get_settings

log = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

INVALIDATION_CHANNEL = "ty:cache:inv"
L1_MAXSIZE = 2000
L1_MAX_VALUE_BYTES = 64 * 1024
LOCK_TTL_S = 30
LOCK_WAIT_S = 2.0
LOCK_POLL_S = 0.1
EARLY_REFRESH_AT = 0.8
REDIS_RECHECK_S = 30.0


# ── Keys ────────────────────────────────────────────────────────────────────────


def fingerprint(*parts: object) -> str:
    """SHA-256 over the orjson encoding of ``parts`` with sorted keys."""
    return hashlib.sha256(orjson.dumps(list(parts), option=orjson.OPT_SORT_KEYS)).hexdigest()


def norm_text(text: str, *, lower: bool = False) -> str:
    """NFC, trimmed, inner whitespace collapsed; lower-cased for embedding keys."""
    t = " ".join(unicodedata.normalize("NFC", text).split())
    return t.lower() if lower else t


def norm_hour(dt: datetime) -> str:
    """Aware time → the UTC hour it falls in."""
    return _utc(dt).strftime("%Y-%m-%dT%HZ")


def norm_window30(dt: datetime) -> str:
    """Aware time → the start of its UTC 30-minute window."""
    u = _utc(dt)
    return u.replace(minute=0 if u.minute < 30 else 30, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%MZ")


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("cache keys need timezone-aware datetimes")
    return dt.astimezone(UTC)


def to_cell(lat: float, lon: float, res: int = 7) -> str:
    """Coordinates → H3 cell. Raw coordinates never enter a cache key."""
    import h3  # type: ignore[import-untyped]

    return str(h3.latlng_to_cell(lat, lon, res))


_CONFIG_FILES = ("constraints.yaml", "boats.yaml", "qc.yaml")


def compute_config_version(config_dir: Path) -> str:
    """SHA-256 of the safety config + phrase files. Changing any threshold changes every dependent key."""
    h = hashlib.sha256()
    files = [config_dir / f for f in _CONFIG_FILES]
    phrases = config_dir / "phrases"
    if phrases.is_dir():
        files += sorted(phrases.glob("*.yaml"))
    for f in files:
        if f.is_file():
            h.update(f.relative_to(config_dir).as_posix().encode())
            h.update(b"\0")
            h.update(f.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


@functools.lru_cache(maxsize=1)
def config_version() -> str:
    """Computed once per process (the `conf` namespace lives for the process lifetime)."""
    return compute_config_version(find_config_dir())


# ── Metrics (no-op when OpenTelemetry is absent) ────────────────────────────────


class _Metrics:
    def __init__(self) -> None:
        self._counter: Any = None
        try:
            from opentelemetry import metrics

            self._counter = metrics.get_meter("ty_common.cache").create_counter(
                "ty.cache.result", description="Cache outcomes per namespace and tier"
            )
        except ImportError:  # pragma: no cover - otel optional
            self._counter = None

    def record(self, ns: str, tier: str, outcome: str) -> None:
        _outcome.set(outcome)
        if self._counter is not None:
            self._counter.add(1, {"ns": ns, "tier": tier, "outcome": outcome})


_metrics = _Metrics()
_outcome: ContextVar[str] = ContextVar("ty_cache_outcome", default="miss")


def last_outcome() -> str:
    """Outcome of the most recent cached call in this task: hit, miss, stale or early."""
    return _outcome.get()


# ── The cache ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Entry:
    value: Any
    stored_at: float  # epoch seconds
    ttl: int


def _ttu(_key: str, entry: _Entry, now: float) -> float:
    return now + max(0.0, entry.stored_at + entry.ttl - time.time())


def _mark_stale(value: Any) -> Any:
    if isinstance(value, dict):
        return value | {"cache": "stale"}
    return value


class Cache:
    """One instance per process. Tests may create several to simulate several processes."""

    def __init__(self, client: aioredis.Redis | None = None, *, disabled: bool | None = None) -> None:
        self._client = client
        self._disabled = disabled
        self.l1: TLRUCache[str, _Entry] = TLRUCache(maxsize=L1_MAXSIZE, ttu=_ttu, timer=time.monotonic)
        self._bg: set[asyncio.Task[None]] = set()
        self._listener: asyncio.Task[None] | None = None
        self._redis_ok = True
        self._ping_at = -REDIS_RECHECK_S

    # wiring
    @property
    def redis(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                get_settings().redis_url.get_secret_value(), socket_connect_timeout=0.5, socket_timeout=2
            )
        return self._client

    @property
    def disabled(self) -> bool:
        return get_settings().cache_disabled if self._disabled is None else self._disabled

    async def redis_available(self) -> bool:
        """Ping at most every 30 s. When Redis is down, calls go straight to the source (no cache)."""
        now = time.monotonic()
        if now - self._ping_at < REDIS_RECHECK_S:
            return self._redis_ok
        self._ping_at = now
        try:
            await self.redis.ping()
            ok = True
        except (RedisError, OSError):
            ok = False
        if not ok and self._redis_ok:
            log.warning("redis unreachable: cache bypassed for %ss", REDIS_RECHECK_S)
        self._redis_ok = ok
        return ok

    # L1 helpers
    def _l1_get(self, k: str) -> _Entry | None:
        return self.l1.get(k)

    def _l1_put(self, k: str, entry: _Entry, size: int) -> None:
        if size <= L1_MAX_VALUE_BYTES:
            self.l1[k] = entry

    def drop_local(self, keys: Iterable[str]) -> None:
        for k in keys:
            self.l1.pop(k, None)

    # L2 helpers
    @staticmethod
    def _encode(entry: _Entry) -> bytes:
        return orjson.dumps({"v": entry.value, "t": entry.stored_at, "ttl": entry.ttl})

    @staticmethod
    def _decode(raw: bytes | str) -> _Entry:
        d = orjson.loads(raw)
        return _Entry(value=d["v"], stored_at=float(d["t"]), ttl=int(d["ttl"]))

    async def _store(self, k: str, value: Any, ttl: int, tags: list[str], l1: bool) -> None:
        entry = _Entry(value=value, stored_at=time.time(), ttl=ttl)
        blob = self._encode(entry)
        pipe = self.redis.pipeline(transaction=False)
        pipe.set(k, blob, ex=ttl)
        pipe.set(f"lastgood:{k}", blob)
        for t in tags:
            pipe.sadd(f"tag:{t}", k, f"lastgood:{k}")
        await pipe.execute()
        if l1:
            self._l1_put(k, entry, len(blob))

    async def _stale(self, k: str) -> tuple[bool, Any]:
        raw = await self.redis.get(f"lastgood:{k}")
        if raw is None:
            return False, None
        return True, _mark_stale(self._decode(raw).value)

    # early refresh
    def _maybe_refresh(
        self, k: str, entry: _Entry, compute: Callable[[], Awaitable[Any]], tags: list[str], l1: bool, ns: str
    ) -> None:
        if time.time() - entry.stored_at < EARLY_REFRESH_AT * entry.ttl:
            return

        async def refresh() -> None:
            try:
                if not await self.redis.set(f"refresh:{k}", 1, nx=True, ex=LOCK_TTL_S):
                    return
                try:
                    value = await compute()
                    await self._store(k, value, entry.ttl, tags, l1)
                    _metrics.record(ns, "compute", "early")
                finally:
                    await self.redis.delete(f"refresh:{k}")
            except Exception:  # background refresh must never crash the caller
                log.warning("early refresh failed for %s", k.split(":")[0], exc_info=True)

        task = asyncio.create_task(refresh())
        self._bg.add(task)
        task.add_done_callback(self._bg.discard)

    async def drain(self) -> None:
        """Wait for background refreshes (tests and graceful shutdown)."""
        while self._bg:
            await asyncio.gather(*list(self._bg), return_exceptions=True)

    # read path
    async def get_or_compute(
        self,
        ns: str,
        k: str,
        ttl: int,
        compute: Callable[[], Awaitable[Any]],
        tags: list[str],
        l1: bool,
    ) -> Any:
        _outcome.set("miss")
        if self.disabled or not await self.redis_available():
            return await compute()

        if l1 and (entry := self._l1_get(k)) is not None:
            _metrics.record(ns, "l1", "hit")
            self._maybe_refresh(k, entry, compute, tags, l1, ns)
            return entry.value

        if (raw := await self.redis.get(k)) is not None:
            entry = self._decode(raw)
            if l1:
                self._l1_put(k, entry, len(raw))
            _metrics.record(ns, "l2", "hit")
            self._maybe_refresh(k, entry, compute, tags, l1, ns)
            return entry.value

        owner = bool(await self.redis.set(f"lock:{k}", 1, nx=True, ex=LOCK_TTL_S))
        if not owner:
            waited = 0.0
            while waited < LOCK_WAIT_S:
                await asyncio.sleep(LOCK_POLL_S)
                waited += LOCK_POLL_S
                if (raw := await self.redis.get(k)) is not None:
                    entry = self._decode(raw)
                    if l1:
                        self._l1_put(k, entry, len(raw))
                    _metrics.record(ns, "l2", "hit")
                    return entry.value
            found, stale = await self._stale(k)
            if found:
                _metrics.record(ns, "l2", "stale")
                return stale
            # owner is slow and nothing is stored: compute ourselves rather than fail

        try:
            try:
                value = await compute()
            except Exception:
                found, stale = await self._stale(k)
                if found:
                    _metrics.record(ns, "l2", "stale")
                    return stale
                raise
            await self._store(k, value, ttl, tags, l1)
            _metrics.record(ns, "compute", "miss")
            return value
        finally:
            if owner:
                await self.redis.delete(f"lock:{k}")

    # invalidation
    async def invalidate(self, *, tag: str | None = None, keys: Iterable[str] = ()) -> int:
        """Delete every key under ``tag`` (and/or explicit keys) from L2 and from L1 in every process."""
        targets = list(keys)
        if tag is not None:
            members = await self.redis.smembers(f"tag:{tag}")
            targets += [m.decode() if isinstance(m, bytes) else str(m) for m in members]
        if targets:
            await self.redis.delete(*targets)
        if tag is not None:
            await self.redis.delete(f"tag:{tag}")
        self.drop_local(targets)
        if targets:
            await self.redis.publish(INVALIDATION_CHANNEL, orjson.dumps(targets))
        return len(targets)

    async def start_listener(self) -> None:
        """Subscribe to ``ty:cache:inv`` and drop matching L1 keys. Call once at service start-up."""
        if self._listener is not None:
            return
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(INVALIDATION_CHANNEL)

        async def listen() -> None:
            try:
                while True:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg is not None and msg.get("type") == "message":
                        self.drop_local(orjson.loads(msg["data"]))
            except asyncio.CancelledError:
                await pubsub.unsubscribe(INVALIDATION_CHANNEL)
                await pubsub.aclose()  # type: ignore[no-untyped-call]
                raise

        self._listener = asyncio.create_task(listen())

    async def stop_listener(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            try:
                await self._listener
            except asyncio.CancelledError:
                pass
            self._listener = None


_default: Cache | None = None


def get_cache() -> Cache:
    global _default
    if _default is None:
        _default = Cache()
    return _default


def set_cache(cache: Cache | None) -> None:
    """Replace the process-wide cache (tests)."""
    global _default
    _default = cache


def cached(
    ns: str,
    ttl: int,
    key: Callable[P, str],
    tags: Callable[P, list[str]] | None = None,
    l1: bool = True,
    schema: int = 1,
    cache: Cache | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Read-through two-tier cache with stampede lock, early refresh, stale-if-error and tags.

    ``key`` returns a fingerprint of everything the result depends on (input data versions, config
    version, normalised args). Never cache free-text LLM replies or personal data.
    """

    def deco(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            c = cache or get_cache()
            k = f"{ns}:v{schema}:{key(*args, **kwargs)}"
            t = tags(*args, **kwargs) if tags else []
            result: R = await c.get_or_compute(ns, k, ttl, lambda: fn(*args, **kwargs), t, l1)
            return result

        return wrapper

    return deco


async def invalidate(*, tag: str | None = None, keys: Iterable[str] = ()) -> int:
    return await get_cache().invalidate(tag=tag, keys=keys)
