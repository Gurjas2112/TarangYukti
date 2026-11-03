"""Term canonicalisation (spec §6.2.8): every spelling → one slug, deterministically, no LLM.

Used for query normalisation, `kb_chunks.topics` at ingest, and spoken harbour names → harbour id.
"""

from __future__ import annotations

import functools
import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from .settings import find_config_dir


def norm(raw: str) -> str:
    """NFKC + collapsed whitespace + casefold."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", raw)).strip().casefold()


@functools.lru_cache(maxsize=4)
def _load(path: str) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    table: dict[str, str] = {}
    terms: dict[str, dict[str, Any]] = doc["terms"]
    for slug, t in terms.items():
        for spelling in [slug, t.get("name", slug), *t.get("aliases", [])]:
            key = norm(str(spelling))
            if key in table and table[key] != slug:
                raise ValueError(f"alias {spelling!r} maps to both {table[key]!r} and {slug!r}")
            table[key] = slug
    return table, terms


def table(config_dir: Path | None = None) -> dict[str, str]:
    return _load(str((config_dir or find_config_dir()) / "aliases.yaml"))[0]


def terms(config_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    return _load(str((config_dir or find_config_dir()) / "aliases.yaml"))[1]


def canonical(raw: str, tbl: dict[str, str] | None = None) -> str | None:
    """The slug for one spelling, or None (unknown terms pass through unchanged)."""
    return (tbl if tbl is not None else table()).get(norm(raw))


def find_topics(text: str, tbl: dict[str, str] | None = None) -> list[str]:
    """Slugs of every alias that occurs in the text (word-bounded for Latin script)."""
    t = norm(text)
    found = set()
    for alias, slug in (tbl if tbl is not None else table()).items():
        if alias.isascii():
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", t):
                found.add(slug)
        elif alias in t:
            found.add(slug)
    return sorted(found)


def expand_query(query: str, tbl: dict[str, str] | None = None) -> str:
    """Append the canonical names of any aliases in the query ("vanjiram ban" also finds "Seer fish")."""
    tm = terms()
    extra = [str(tm[s].get("name", s)) for s in find_topics(query, tbl)]
    return " ".join([query, *[e for e in extra if norm(e) not in norm(query)]])
