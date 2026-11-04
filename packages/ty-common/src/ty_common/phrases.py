"""Approved safety wording (config/phrases/<lang>.yaml) and the language list (config/languages.yaml).

Safety sentences come only from these files (rule 6). A phrase file is used for a language when it exists and the
language is available in this environment (released in `live`; every language in local, ci and preview builds),
otherwise English. The LLM and machine translation never write these sentences.
"""

from __future__ import annotations

import functools
import hashlib
from pathlib import Path
from typing import Any

import yaml

from .settings import find_config_dir, get_settings


@functools.cache
def languages() -> list[dict[str, Any]]:
    doc = yaml.safe_load((find_config_dir() / "languages.yaml").read_text(encoding="utf-8"))
    return list(doc["languages"])


def available_languages() -> list[dict[str, Any]]:
    """Languages users may pick here: released ones in `live`, all of them elsewhere (staging and capture)."""
    if get_settings().env == "live":
        return [lang for lang in languages() if lang["status"] == "released"]
    return languages()


def language(code: str) -> dict[str, Any] | None:
    return next((lang for lang in languages() if lang["code"] == code), None)


def nearest_language(locale: str | None) -> str:
    """Nearest available language to a device locale ('ta', 'ta-IN', 'en-GB' …). No hard-coded default:
    falls back to the first available language whose base matches, else the first available language."""
    avail = available_languages()
    if locale:
        base = locale.replace("_", "-").split("-")[0].lower()
        for lang in avail:
            if lang["code"].lower() == locale.lower():
                return str(lang["code"])
        for lang in avail:
            if lang["code"].split("-")[0].lower() == base:
                return str(lang["code"])
    if not avail:
        raise RuntimeError("no language is available in this environment")
    return str(avail[0]["code"])


def _file(lang: str) -> Path:
    return find_config_dir() / "phrases" / f"{lang.split('-')[0]}.yaml"


@functools.cache
def load(lang: str) -> dict[str, Any] | None:
    p = _file(lang)
    if not p.is_file():
        return None
    doc: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))
    if get_settings().env == "live" and doc.get("status") != "approved":
        return None
    return doc


def phrases(lang: str) -> tuple[dict[str, Any], str]:
    """(phrase table, the language actually used)."""
    doc = load(lang)
    if doc is not None:
        return doc, lang
    en = load("en-IN")
    if en is None:
        raise RuntimeError("config/phrases/en.yaml is missing or not approved")
    return en, "en-IN"


def footer(lang: str) -> str:
    return str(phrases(lang)[0]["footer"])


@functools.cache
def phrases_version() -> str:
    h = hashlib.sha256()
    for f in sorted((find_config_dir() / "phrases").glob("*.yaml")):
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


@functools.cache
def harbours() -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load((find_config_dir() / "harbours.yaml").read_text(encoding="utf-8"))
    return {h["id"]: {**h, "suggested_language": doc["suggested_language"].get(h["state"])} for h in doc["harbours"]}


def harbour(harbour_id: str) -> dict[str, Any]:
    h = harbours().get(harbour_id)
    if h is None:
        raise ValueError(f"unknown harbour {harbour_id!r}")
    return h
