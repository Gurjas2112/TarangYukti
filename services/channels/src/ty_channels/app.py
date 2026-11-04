"""ty-channels FastAPI app (:8002): the voice and device API used by the app on Android and the web.

Public: /health, /languages, /harbours, /brief, /stt, /tts (rate-limited).
Expert + analyst (public): /expert/plan, /layers/*, /grids/*, /pfz, /anomaly, /sources/chunk/*, /kb/documents.
Signed in: /onboarding, /me, /me/prefs, /push/subscribe, /push/unsubscribe, /phone-link,
/positions, /trips, /trips/back, /trips/{id}/feedback, /share, /family.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ty_common import db
from ty_common.settings import get_settings

from . import expert, me, public, trips, voice


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if get_settings().database_url is not None:
        await db.open_pool()
    yield
    await db.close_pool()


settings = get_settings()
app = FastAPI(title="ty-channels", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(public.router)
app.include_router(voice.router)
app.include_router(me.router)
app.include_router(expert.router)
app.include_router(trips.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
