"""Rate limits in Redis (spec §9.2): anonymous 20 questions/hour/IP, signed-in 60/hour.

Keys hold a salted hash of the IP or the user id, never the raw value. If Redis is down the limit is not
enforced (logged): the prototype prefers answering a fisher over refusing one.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import HTTPException, Request
from redis.exceptions import RedisError
from ty_common.cache import get_cache

log = logging.getLogger(__name__)
ANON_PER_HOUR = 20
USER_PER_HOUR = 60


def who(request: Request, claims: dict[str, Any] | None) -> tuple[str, int]:
    if claims is not None:
        return "u:" + hashlib.sha256(str(claims["sub"]).encode()).hexdigest()[:24], USER_PER_HOUR
    ip = request.headers.get("x-azure-clientip") or (request.client.host if request.client else "unknown")
    return "ip:" + hashlib.sha256(f"ty-rl:{ip}".encode()).hexdigest()[:24], ANON_PER_HOUR


async def check(request: Request, claims: dict[str, Any] | None, bucket: str = "q") -> None:
    name, limit = who(request, claims)
    cache = get_cache()
    if cache.disabled or not await cache.redis_available():
        return
    key = f"rl:{bucket}:{name}"
    try:
        pipe = cache.redis.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, 3600, nx=True)
        n, _ = await pipe.execute()
    except (RedisError, OSError):
        log.warning("rate limit skipped: redis error")
        return
    if int(n) > limit:
        raise HTTPException(429, "too many requests, try again in an hour", headers={"Retry-After": "3600"})
