"""HTTP for data tools: allow-listed domains only (config/sources.yaml), timeouts, redirects re-checked."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx

from . import config

USER_AGENT = "TarangYukti/0.1 (+https://github.com/Gurjas2112/TarangYukti; research prototype)"


class SourceUnavailable(Exception):
    """The live source cannot answer (down, blocked, not whitelisted or no machine-readable feed)."""


class NotAllowed(SourceUnavailable):
    pass


def allowed(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in config.sources()["allowlist_domains"])


async def get_json(url: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
    if not allowed(url):
        raise NotAllowed(f"domain not in config/sources.yaml allow-list: {urlsplit(url).hostname}")
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            r = await client.get(url, params=params)
            if not allowed(str(r.url)):
                raise NotAllowed(f"redirected outside the allow-list: {r.url.host}")
            r.raise_for_status()
            return r.json()
    except NotAllowed:
        raise
    except (httpx.HTTPError, ValueError) as e:
        raise SourceUnavailable(f"{urlsplit(url).hostname}: {type(e).__name__}: {e}") from e
