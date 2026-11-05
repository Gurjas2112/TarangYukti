"""App release info and client error reports (spec §17.12).

- GET /app/version → {latestVersionCode, minVersionCode, apkUrl, sha256}: the app shows an update banner, and a
  full-screen prompt below minVersionCode (alerts keep working). Values come from the deployment environment.
- POST /client-errors → JavaScript errors from every install land in the logs (Application Insights in Tier 1).
  Rate-limited; messages are truncated and stripped of anything that looks like coordinates or e-mail addresses.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from ty_common import capture
from ty_common.auth import current_user

from . import limits
from .public import PUBLIC_CACHE

router = APIRouter()
log = logging.getLogger("ty.client")
SCRUB = [
    (re.compile(r"-?\d{1,3}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}"), "<coords>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<email>"),
    (re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"), "<token>"),
]


def scrub(text: str) -> str:
    for pattern, repl in SCRUB:
        text = pattern.sub(repl, text)
    return text


def _min_version() -> int:
    if capture.active("update-required"):  # walkthrough scenario: every installed build is below the minimum
        return 1_000_000
    return int(os.environ.get("APP_MIN_VERSION_CODE", "1"))


@router.get("/app/version")
async def app_version(response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return {
        "latestVersionCode": int(os.environ.get("APP_LATEST_VERSION_CODE", "1")),
        # walkthrough scenario: every installed build is below the minimum
        "minVersionCode": 1_000_000
        if capture.active("update-required")
        else int(os.environ.get("APP_MIN_VERSION_CODE", "1")),
        "apkUrl": os.environ.get("APP_APK_URL") or None,
        "sha256": os.environ.get("APP_APK_SHA256") or None,
    }


class ClientError(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    message: Annotated[str, StringConstraints(max_length=1000)]
    stack: Annotated[str, StringConstraints(max_length=4000)] | None = None
    platform: Literal["android", "web"]
    version: Annotated[str, StringConstraints(max_length=40)]
    screen: Annotated[str, StringConstraints(max_length=80)] | None = Field(default=None)


@router.post("/client-errors", status_code=204)
async def client_errors(
    body: ClientError,
    request: Request,
    claims: dict[str, Any] | None = Depends(current_user),  # noqa: B008
) -> Response:
    await limits.check(request, claims, bucket="client-errors")
    log.warning(
        "client error",
        extra={
            "platform": body.platform,
            "app_version": body.version,
            "screen": body.screen,
            "error": scrub(body.message),
            "stack": scrub(body.stack or "")[:4000],
        },
    )
    return Response(status_code=204)
