"""POST /admin/capture/scenario (spec §17.14.3): laptop-only states for the walkthrough capture.

Exists only with ENV=local and CAPTURE_SCENARIOS=1 (404 everywhere else, including Tier 1) and needs the
X-Capture-Token header. `fault-next-request` makes exactly one following request fail with 500, then resets.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from ty_common import capture
from ty_common.settings import get_settings

router = APIRouter()


class ScenarioIn(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    name: str


@router.post("/admin/capture/scenario")
async def set_scenario(body: ScenarioIn, x_capture_token: str | None = Header(default=None)) -> dict[str, Any]:
    token = get_settings().capture_token
    if not capture.enabled() or token is None:
        raise HTTPException(404)
    if not x_capture_token or not hmac.compare_digest(x_capture_token, token.get_secret_value()):
        raise HTTPException(403, "bad capture token")
    if body.name not in capture.NAMES:
        raise HTTPException(422, f"unknown scenario; one of {list(capture.NAMES)}")
    capture.set_scenario(body.name)
    return {"scenario": body.name}


class CaptureFault(BaseHTTPMiddleware):
    """The `fault-next-request` scenario: the next request (other than health and capture) fails once with 500."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if capture.active("fault-next-request") and path not in ("/health", "/admin/capture/scenario"):
            capture.set_scenario("normal")
            return JSONResponse({"detail": "capture scenario: one simulated server error"}, status_code=500)
        return await call_next(request)
