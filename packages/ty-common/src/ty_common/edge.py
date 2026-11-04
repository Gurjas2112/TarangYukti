"""Front Door-only access (spec §15.2.1). Front Door adds `X-Azure-FDID` (its profile id) to every request it
forwards; when FRONTDOOR_ID is set, any other request gets 403. Health paths stay open for the platform's probes.
Unset (laptop, slim demo tier without Front Door) = no check."""

from __future__ import annotations

import os
from collections.abc import Iterable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp


class FrontDoorOnly(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, exempt: Iterable[str] = ("/health", "/ok"), fdid: str | None = None) -> None:
        super().__init__(app)
        self.fdid = fdid if fdid is not None else (os.environ.get("FRONTDOOR_ID") or None)
        self.exempt = frozenset(exempt)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self.fdid and request.url.path not in self.exempt and request.headers.get("x-azure-fdid") != self.fdid:
            return PlainTextResponse("forbidden", status_code=403)
        return await call_next(request)
