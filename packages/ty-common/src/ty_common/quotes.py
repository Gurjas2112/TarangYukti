"""Verbatim quote check (spec §6.2.7): a cited quote must be an exact span of the cited chunk.

Normalisation only removes formatting differences — NFKC, curly quotes and dashes, whitespace — never
words. Quotes shorter than MIN_CHARS are rejected: they prove nothing.
"""

from __future__ import annotations

import re
import unicodedata

MIN_CHARS = 12
_TRANS = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",  # single quotes
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',  # double quotes
        "–": "-",
        "—": "-",
        "−": "-",  # en dash, em dash, minus
        " ": " ",  # no-break space
    }
)


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(_TRANS)
    return re.sub(r"\s+", " ", t).strip()


def is_verbatim(chunk_text: str, quote: str, *, min_chars: int = MIN_CHARS) -> bool:
    """True iff `quote` is long enough and appears word for word in `chunk_text` (spec §6.2.7 signature)."""
    if not chunk_text or not quote:
        return False
    q = normalise(quote)
    return len(q) >= min_chars and q in normalise(chunk_text)
