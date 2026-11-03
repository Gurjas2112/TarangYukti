"""Gemini Embedding 2 (prompt §3): 768-d, document and query prefixes, one vector per text.

Documents: "title: {title} | text: {content}". Queries: "task: search result | query: {query}".
Query embeddings are cached in namespace `emb` (7 days, key = sha256(normalised text) + model + dim).
"""

from __future__ import annotations

import asyncio
from typing import Any

from .cache import cached, fingerprint, norm_text
from .settings import get_settings

BATCH = 100


def doc_text(title: str | None, content: str) -> str:
    return f"title: {title or 'none'} | text: {content}"


def query_text(query: str) -> str:
    return f"task: search result | query: {query}"


class EmbeddingUnavailable(RuntimeError):
    pass


def _client() -> Any:
    from google import genai

    s = get_settings()
    if s.google_api_key is None:
        raise EmbeddingUnavailable("GOOGLE_API_KEY is not set")
    return genai.Client(api_key=s.google_api_key.get_secret_value())


def embed_sync(texts: list[str]) -> list[list[float]]:
    """One 768-d vector per text (texts already carry their prefix)."""
    from google.genai import types

    s = get_settings()
    client = _client()
    out: list[list[float]] = []
    try:
        for i in range(0, len(texts), BATCH):
            part = texts[i : i + BATCH]
            r = client.models.embed_content(
                model=s.embed_model,
                contents=[types.Content(parts=[types.Part(text=t)]) for t in part],
                config=types.EmbedContentConfig(output_dimensionality=s.embed_dim),
            )
            vecs = [list(e.values) for e in r.embeddings]
            if len(vecs) != len(part):
                raise EmbeddingUnavailable(f"expected {len(part)} vectors, got {len(vecs)}")
            out.extend(vecs)
    except EmbeddingUnavailable:
        raise
    except Exception as e:  # network, quota, auth: the caller falls back to full-text search
        raise EmbeddingUnavailable(f"{type(e).__name__}: {e}") from e
    return out


@cached(
    ns="emb",
    ttl=7 * 86400,
    key=lambda query: fingerprint(
        norm_text(query, lower=True), get_settings().embed_model, get_settings().embed_dim
    ),
)
async def embed_query(query: str) -> list[float]:
    vecs = await asyncio.to_thread(embed_sync, [query_text(norm_text(query))])
    return vecs[0]
