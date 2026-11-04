"""Supabase JWT verification (spec §9.1.1): asymmetric keys from the project JWKS, audience and issuer checked.

No token = anonymous (public safety answers only). A bad token = 401.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request

from .settings import get_settings

ALGORITHMS = ["ES256", "RS256"]


@functools.cache
def _jwks() -> jwt.PyJWKClient:
    s = get_settings()
    url = s.supabase_jwks_url or f"{s.supabase_url}/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=600)


def verify(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        key = _jwks().get_signing_key_from_jwt(token).key
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=ALGORITHMS,
            audience="authenticated",
            issuer=f"{s.supabase_url}/auth/v1",
            leeway=60,
        )
    except (jwt.PyJWTError, jwt.PyJWKClientError) as e:
        raise HTTPException(401, "invalid token") from e
    return claims


def current_user(request: Request) -> dict[str, Any] | None:
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    return verify(token) if token else None


def require(*roles: str, mfa: bool = False) -> Callable[..., dict[str, Any]]:
    def dep(claims: dict[str, Any] | None = Depends(current_user)) -> dict[str, Any]:  # noqa: B008
        if claims is None:
            raise HTTPException(401, "login required for this feature")
        if mfa and claims.get("aal") != "aal2":
            raise HTTPException(403, "multi-factor authentication required")
        if roles and claims.get("app_role") not in roles:
            raise HTTPException(403, "insufficient role")
        return claims

    return dep
