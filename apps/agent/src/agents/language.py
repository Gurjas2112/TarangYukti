"""Language agent (spec §6.5): pick and keep the reply language; translate validated English drafts.

- The language is the one the app sends (user_prefs.language or the device locale), else the script of the
  message mapped through config/languages.yaml, else the first released language. Outside ENV=live, draft
  languages are allowed too (none is released before two native-speaker reviews).
- Free-form replies: English draft → Sarvam sarvam-translate:v1 (formal, international numerals, ≤ 2,000
  characters per request, split at sentence boundaries) → the numbers and times must be identical, else the
  English text is sent. Safety sentences come from config/phrases only (templates.py), never from here.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
from collections import Counter
from typing import Any

import yaml
from ty_common.settings import find_config_dir, get_settings

log = logging.getLogger(__name__)
MAX_CHARS = 2000


@functools.cache
def languages() -> list[dict[str, Any]]:
    doc = yaml.safe_load((find_config_dir() / "languages.yaml").read_text(encoding="utf-8"))
    langs: list[dict[str, Any]] = doc["languages"]
    return langs


def available() -> list[dict[str, Any]]:
    live = get_settings().env == "live"
    return [x for x in languages() if x["status"] == "released" or not live]


def script_for(lang: str) -> str:
    for x in languages():
        if x["code"] == lang:
            return str(x["script"])
    return "Latn"


def sarvam_code(lang: str) -> str:
    for x in languages():
        if x["code"] == lang:
            return str(x["sarvam_code"])
    return lang


def detect(text: str) -> str | None:
    """The language for the dominant non-Latin script of the text (first matching entry), else None."""
    from ..validator import SCRIPTS

    counts = {s: len(re.findall(p, text)) for s, p in SCRIPTS.items() if s != "Latn"}
    script, n = max(counts.items(), key=lambda kv: kv[1])
    if n == 0:
        if not re.search(SCRIPTS["Latn"], text):
            return None
        script = "Latn"  # Latin letters only: the language written in Latin script
    return next((x["code"] for x in available() if x["script"] == script), None)


def choose(requested: str | None, current: str | None, message: str) -> str:
    codes = {x["code"] for x in available()}
    if requested in codes:
        return str(requested)
    detected = detect(message)
    latin = detected is not None and next((x["script"] for x in available() if x["code"] == detected), "") == "Latn"
    if detected and not (latin and current in codes):
        return detected  # a short Latin reply ("ok") is not confident enough to leave the stored language
    if current in codes:
        return str(current)
    from ty_common.phrases import nearest_language

    return nearest_language(None)  # config order decides, never a hard-coded language


MARKER = re.compile(r"\s*\[K\d+\]")
SENTENCE = re.compile(r"(?<=[.!?।])\s+")
DIGITS = re.compile(r"\d+(?:[.:]\d+)?")


def _numbers(text: str) -> Counter[str]:
    """Every number and time, digit for digit. Units are compared as words in English only: a translation must
    keep "5" and "05:30" identical, but it is supposed to translate "km" (கி.மீ., کلومیٹر …)."""

    def norm(x: str) -> str:
        if ":" in x:  # "05:30" and "5:30" are the same time
            h, m = x.split(":")
            return f"{int(h)}:{m}"
        return x

    return Counter(norm(m.group()) for m in DIGITS.finditer(text))


def split_sentences(text: str, limit: int = MAX_CHARS) -> list[str]:
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text):
        if cur and len(cur) + len(s) + 1 > limit:
            parts.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        parts.append(cur)
    return parts


async def translate(text: str, lang: str) -> tuple[str, str | None]:
    """(text in `lang`, None) or (the English text, reason) when translation is unavailable or changed a number."""
    if lang.startswith("en"):
        return text, None
    s = get_settings()
    if s.sarvam_api_key is None:
        return text, "translation unavailable (no SARVAM_API_KEY)"

    from sarvamai import SarvamAI

    client = SarvamAI(api_subscription_key=s.sarvam_api_key.get_secret_value())

    def one(sentence: str) -> str:
        # Citation markers ([K3]) are taken out before translating and put back after the sentence: some
        # languages drop them, and a sentence must never lose the link to its source document.
        marks = [m.strip() for m in MARKER.findall(sentence)]
        clean = MARKER.sub("", sentence).strip()
        if not clean:
            return " ".join(marks)
        out = []
        for part in split_sentences(clean):
            r = client.text.translate(
                input=part,
                source_language_code="en-IN",
                target_language_code=sarvam_code(lang),
                model="sarvam-translate:v1",
                mode="formal",
                numerals_format="international",
            )
            out.append(r.translated_text)
        return " ".join([*out, *marks])

    sentences = [x for x in SENTENCE.split(text.strip()) if x.strip()]
    try:
        parts = await asyncio.wait_for(asyncio.gather(*(asyncio.to_thread(one, x) for x in sentences)), timeout=20)
        translated = " ".join(parts)
    except Exception as e:  # network, quota: send English rather than nothing
        log.info("translation failed: %s", type(e).__name__)
        return text, f"translation unavailable ({type(e).__name__})"
    if _numbers(translated) != _numbers(text):
        return text, "translation changed a number or time; English sent instead"
    return translated, None
