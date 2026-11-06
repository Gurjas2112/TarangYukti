"""POST /admin/capture/scenario (spec §17.14.3): laptop-only states for the walkthrough capture.

Exists only with ENV=local and CAPTURE_SCENARIOS=1 (404 everywhere else, including Tier 1) and needs the
X-Capture-Token header. `fault-next-request` makes the next brief requests (the Today screen's data) fail with 500
FAULT_TIMES times — the app's own automatic retries included — so the error and its Try again button show; then resets.
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
FAULT_TIMES = 2  # the first request plus useBrief's one automatic retry (apps/app/src/brief/useBrief.ts)
_faults = {"left": 0}


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
    _faults["left"] = FAULT_TIMES if body.name == "fault-next-request" else 0
    return {"scenario": body.name}


class CaptureFault(BaseHTTPMiddleware):
    """The `fault-next-request` scenario: the next /brief request fails once with 500 (the app shows Try again)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if capture.active("fault-next-request") and path.startswith("/brief") and _faults["left"] > 0:
            _faults["left"] -= 1
            if _faults["left"] == 0:
                capture.set_scenario("normal")
            return JSONResponse({"detail": "capture scenario: one simulated server error"}, status_code=500)
        response = await call_next(request)
        if capture.enabled():  # scenarios change answers between flows: never let the phone reuse a cached one
            response.headers["Cache-Control"] = "no-store"
        return response
