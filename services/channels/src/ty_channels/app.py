"""ty-channels FastAPI app (:8002). /stt, /tts, /positions, /push/subscribe, /trips arrive in Milestone 6+."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ty_common.settings import get_settings

settings = get_settings()
app = FastAPI(title="ty-channels", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
