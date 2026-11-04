"""Voice in and out (spec §6.5): Sarvam Saaras v4 speech-to-text, Bulbul v3 text-to-speech (mp3).

- /stt: up to 60 s of audio in any of the 23 languages; audio and transcript are never stored or cached.
- /tts: Group A languages only (Group B gets text). Audio is cached by sha256(text, voice, model) as a public
  Supabase Storage object (bucket `tts`) with a 30-day Redis pointer (`tts` namespace), so approved phrases and
  shared briefs are synthesised once.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sarvamai import AsyncSarvamAI
from ty_common.auth import current_user
from ty_common.cache import cached, fingerprint, norm_text
from ty_common.phrases import available_languages, language
from ty_common.settings import get_settings

from . import limits

router = APIRouter()
STT_MODEL, TTS_MODEL, VOICE = "saaras:v4", "bulbul:v3", "shubh"
MAX_AUDIO_BYTES = 2_000_000  # about 60 s of compressed speech
KEYTERMS = ["IMBL", "PFZ", "INCOIS", "IMD", "Rameswaram", "Mandapam", "Pamban", "Thoothukudi"]


def _client() -> AsyncSarvamAI:
    key = get_settings().sarvam_api_key
    if key is None:
        raise HTTPException(503, "voice is not configured")
    return AsyncSarvamAI(api_subscription_key=key.get_secret_value())


def _lang(code: str) -> dict[str, Any]:
    lang = language(code)
    if lang is None or code not in {x["code"] for x in available_languages()}:
        raise HTTPException(422, f"language {code!r} is not available")
    return lang


@router.post("/stt")
async def stt(
    request: Request,
    audio: UploadFile = File(...),  # noqa: B008
    lang: str = Form(...),
    claims: dict[str, Any] | None = Depends(current_user),  # noqa: B008
) -> dict[str, Any]:
    await limits.check(request, claims)
    lg = _lang(lang)
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "voice notes are limited to 60 seconds")
    r = await _client().speech_to_text.transcribe(
        file=(audio.filename or "voice.m4a", data, audio.content_type or "audio/mp4"),
        model=STT_MODEL,
        mode="codemix",
        language_code=lg["sarvam_code"],
        keyterms=KEYTERMS,
    )
    detected = getattr(r, "language_code", None)
    # switch only to an available language Saaras identified; otherwise keep the user's choice
    code = next((x["code"] for x in available_languages() if x["sarvam_code"] == detected), lg["code"])
    return {"text": r.transcript, "lang": code}


class TtsIn(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    text: str = Field(min_length=1, max_length=1500)
    lang: str


def object_name(text: str, sarvam_code: str) -> str:
    return hashlib.sha256(f"{text}|{sarvam_code}|{VOICE}|{TTS_MODEL}".encode()).hexdigest() + ".mp3"


async def _upload(name: str, mp3: bytes) -> str:
    s = get_settings()
    key = s.supabase_service_role_key
    if key is None:
        raise HTTPException(503, "storage is not configured")
    k = key.get_secret_value()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            f"{s.supabase_url}/storage/v1/object/tts/{name}",
            content=mp3,
            headers={
                "apikey": k,
                "Authorization": f"Bearer {k}",
                "Content-Type": "audio/mpeg",
                "x-upsert": "true",
            },
        )
        r.raise_for_status()
    return f"{s.supabase_url}/storage/v1/object/public/tts/{name}"


@cached(
    ns="tts",
    ttl=30 * 86400,
    key=lambda text, sarvam_code: fingerprint("tts", text, sarvam_code, VOICE, TTS_MODEL),
)
async def synthesise(text: str, sarvam_code: str) -> dict[str, str]:
    r = await _client().text_to_speech.convert(
        text=text, language_code=sarvam_code, speaker=VOICE, model=TTS_MODEL, output_audio_codec="mp3"
    )
    mp3 = b"".join(base64.b64decode(a) for a in r.audios)
    return {"url": await _upload(object_name(text, sarvam_code), mp3)}


@router.post("/tts")
async def tts(
    body: TtsIn,
    request: Request,
    claims: dict[str, Any] | None = Depends(current_user),  # noqa: B008
) -> dict[str, Any]:
    lg = _lang(body.lang)
    if lg["group"] != "A":
        return {"url": None, "reason": "no voice for this language, text only"}
    await limits.check(request, claims, bucket="tts")
    out = await synthesise(norm_text(body.text), lg["sarvam_code"])
    return {"url": out["url"]}
