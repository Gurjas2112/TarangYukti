"""kb_search (spec §6.2.4–6.2.6): hybrid, time- and place-filtered document search with citations.

Two queries run — the original (aliases expanded) and an English rewrite (Gemini, low effort) — each through
`kb_hybrid_search` (pgvector + full text, filtered by validity, supersession and region), merged by RRF, top 8.
If embeddings are unavailable the search runs full-text only. If the best cosine similarity is below
RAG_MIN_SIM the result says nothing relevant was found. Results are cached 10 minutes (namespace `kb`), keyed by
the query, the H3 cell, the hour and the index version.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import h3
import psycopg
from psycopg.rows import dict_row
from ty_common import aliases
from ty_common.cache import cached, fingerprint, norm_hour, norm_text
from ty_common.embed import EmbeddingUnavailable, embed_query
from ty_common.models import ToolResult
from ty_common.settings import get_settings

from ..tools.common import now

log = logging.getLogger(__name__)

TOP_N = 8
K = 40
RRF_K = 50
PROMPT = (Path(__file__).parent / "prompts" / "rewrite.md").read_text(encoding="utf-8")
SOURCE = "TarangYukti knowledge base"
STOP = frozenset(
    "a an and are as at be by can do does for from how i in is it me my of on or should the to was what when "
    "where which who why will with you your there this that".split()
)


class SearchUnavailable(Exception):
    pass


# ── database (sync psycopg in a thread: psycopg async needs a selector loop on Windows) ──────────


@functools.cache
def _dsn() -> str:
    s = get_settings()
    if s.database_url is None:
        raise SearchUnavailable("DATABASE_URL is not set")
    return s.database_url.get_secret_value()


def _query(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        with psycopg.connect(
            _dsn(), connect_timeout=15, row_factory=dict_row, options="-c search_path=public,extensions"
        ) as conn:
            with conn.transaction():
                conn.execute("set local role authenticated")  # RLS applies, as for any public reader
                return list(conn.execute(sql.encode(), params).fetchall())
    except psycopg.Error as e:
        raise SearchUnavailable(f"knowledge base unavailable: {type(e).__name__}") from e


async def db(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_query, sql, params or {})


async def index_version() -> int:
    rows = await db("select index_version from kb_index where id = 1")
    return int(rows[0]["index_version"]) if rows else 0


# ── query preparation ────────────────────────────────────────────────────────────


def fts_query(text: str) -> str:
    """OR of the meaningful words, in websearch syntax (an AND of a whole question rarely matches)."""
    words = [w for w in re.findall(r"[\w\-]+", aliases.norm(text)) if len(w) > 2 and w not in STOP]
    return " or ".join(dict.fromkeys(words)) or text


async def rewrite_english(question: str) -> str | None:
    s = get_settings()
    if s.google_api_key is None:
        return None

    def call() -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=s.google_api_key.get_secret_value())  # type: ignore[union-attr]
        r = client.models.generate_content(
            model=s.orca_model,
            contents=PROMPT + question,
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=96,
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            ),
        )
        return (r.text or "").strip().splitlines()[0].strip() if r.text else ""

    try:
        out = await asyncio.wait_for(asyncio.to_thread(call), timeout=min(s.llm_timeout_s, 10))
    except Exception as e:  # rewrite is an optimisation; search still runs on the original
        log.info("query rewrite skipped: %s", type(e).__name__)
        return None
    return out if out and norm_text(out, lower=True) != norm_text(question, lower=True) else None


# ── search ───────────────────────────────────────────────────────────────────────

HYBRID = """
select chunk_id, score, sim
from kb_hybrid_search(%(q_text)s, %(q_emb)s::extensions.vector, %(at)s::timestamptz,
                      case when %(near)s::text is null then null else st_geogfromtext(%(near)s) end,
                      %(k)s, %(rrf_k)s, %(known_at)s::timestamptz)
"""

DETAILS = """
select c.id as chunk_id, c.content, c.heading_path, c.topics, d.id as document_id, d.source_id, d.version,
       d.title, d.issuer, d.doc_type, d.language, d.url, d.licence, d.valid_from, d.valid_to, d.ingested_at
from kb_chunks c join kb_documents d on d.id = c.document_id
where c.id = any(%(ids)s)
"""


@dataclass(frozen=True)
class Hit:
    chunk_id: int
    rrf: float
    sim: float | None


def rrf_merge(lists: list[list[dict[str, Any]]], top: int = TOP_N, rrf_k: int = RRF_K) -> list[Hit]:
    """Reciprocal rank fusion across ranked lists (each already ordered by kb_hybrid_search)."""
    score: dict[int, float] = {}
    sim: dict[int, float | None] = {}
    for rows in lists:
        for rank, r in enumerate(rows, start=1):
            cid = int(r["chunk_id"])
            score[cid] = score.get(cid, 0.0) + 1.0 / (rrf_k + rank)
            s = r.get("sim")
            if s is not None:
                sim[cid] = max(float(s), sim.get(cid) or -1.0)
            else:
                sim.setdefault(cid, None)
    order = sorted(score, key=lambda c: (-score[c], c))[:top]
    return [Hit(c, round(score[c], 6), _round(sim[c])) for c in order]


def _round(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


async def _one(
    text: str, emb: list[float] | None, at: datetime, near: str | None, known_at: datetime
) -> list[dict[str, Any]]:
    return await db(
        HYBRID,
        {
            "q_text": fts_query(text),
            "q_emb": None if emb is None else str(emb),
            "at": at,
            "near": near,
            "k": K,
            "rrf_k": RRF_K,
            "known_at": known_at,
        },
    )


async def _embed(text: str) -> list[float] | None:
    try:
        return await embed_query(text)
    except EmbeddingUnavailable as e:
        log.info("embedding unavailable, full text only: %s", e)
        return None


@cached(
    ns="kb",
    ttl=600,
    key=lambda q, cell, hour, idx, at_iso, known_iso: fingerprint(
        hashlib.sha256(norm_text(q, lower=True).encode()).hexdigest(), cell, hour, idx, at_iso, known_iso
    ),
)
async def _search(q: str, cell: str | None, hour: str, idx: int, at_iso: str, known_iso: str) -> dict[str, Any]:
    at, known_at = datetime.fromisoformat(at_iso), datetime.fromisoformat(known_iso)
    near = None
    if cell:
        lat, lon = h3.cell_to_latlng(cell)
        near = f"SRID=4326;POINT({lon:.5f} {lat:.5f})"
    expanded = aliases.expand_query(q)
    english = await rewrite_english(q)
    queries = [expanded] + ([aliases.expand_query(english)] if english else [])
    embs = await asyncio.gather(*(_embed(x) for x in queries))
    lists = await asyncio.gather(*(_one(x, e, at, near, known_at) for x, e in zip(queries, embs, strict=True)))
    hits = rrf_merge(list(lists))
    details = {int(r["chunk_id"]): r for r in await db(DETAILS, {"ids": [h.chunk_id for h in hits]})} if hits else {}
    min_sim = get_settings().rag_min_sim
    sims = [h.sim for h in hits if h.sim is not None]
    hybrid = all(e is not None for e in embs)
    best = max(sims) if sims else None
    relevant = (best is not None and best >= min_sim) if hybrid else bool(hits)
    chunks = []
    for i, h in enumerate(hits, start=1):
        d = details[h.chunk_id]
        chunks.append(
            {
                "marker": f"K{i}",
                "chunk_id": h.chunk_id,
                "score": h.rrf,
                "sim": h.sim,
                "content": d["content"],
                "heading_path": d["heading_path"],
                "topics": d["topics"],
                "document": {
                    "id": str(d["document_id"]),
                    "source_id": d["source_id"],
                    "version": d["version"],
                    "title": d["title"],
                    "issuer": d["issuer"],
                    "doc_type": d["doc_type"],
                    "language": d["language"],
                    "url": d["url"],
                    "licence": d["licence"],
                    "valid_from": d["valid_from"].isoformat() if d["valid_from"] else None,
                    "valid_to": d["valid_to"].isoformat() if d["valid_to"] else None,
                    "ingested_at": d["ingested_at"].isoformat(),
                },
            }
        )
    return {
        "query": q,
        "expanded_query": expanded,
        "english_query": english,
        "mode": "hybrid" if hybrid else "full_text",
        "relevant": relevant,
        "best_sim": best,
        "min_sim": min_sim,
        "index_version": idx,
        "at": at_iso,
        "known_at": known_iso,
        "chunks": chunks,
    }


async def kb_search(
    query: str,
    lang: str | None = None,
    near_lat: float | None = None,
    near_lon: float | None = None,
    at: str | None = None,
    known_at: str | None = None,
) -> dict[str, Any]:
    """Search official documents (fishing ban order, fishing laws and rules, maritime zones act, CMFRI landings,
    active IMD/INCOIS/SDMA bulletins, safety procedures) and return up to 8 cited passages [K1]…[K8].

    query: the question in any language. near_lat/near_lon: optional position (documents for other regions are
    filtered out beyond 50 km). at: ISO time the answer is about (default now: expired advisories are excluded).
    known_at: replay what was searchable at a past time (default now: superseded documents are excluded).
    `relevant` is false when nothing matches well enough: then say nothing relevant was found and name the
    official source. Quote passages word for word; never paraphrase a quote.
    """
    q = norm_text(query)
    if not q:
        raise ValueError("query is empty")
    t_now = now()
    at_t = datetime.fromisoformat(at) if at else t_now
    known_t = datetime.fromisoformat(known_at) if known_at else t_now
    for t in (at_t, known_t):
        if t.tzinfo is None:
            raise ValueError("times need a timezone, e.g. 2026-11-04T04:00:00+05:30")
    cell = None
    if near_lat is not None and near_lon is not None:
        from .. import qc

        qc.check_region(near_lat, near_lon)
        cell = h3.latlng_to_cell(near_lat, near_lon, 7)  # raw coordinates never reach the cache
    try:
        idx = await index_version()
        data = await _search(q, cell, norm_hour(at_t), idx, at_t.isoformat(), known_t.isoformat())
    except SearchUnavailable as e:
        return ToolResult(
            data={"available": False, "reason": str(e)},
            source=SOURCE,
            source_url="urn:tarangyukti:kb",
            fetched_at=t_now,
            confidence="low",
            notes=[str(e)],
        ).model_dump(mode="json")
    notes = []
    if data["mode"] == "full_text":
        notes.append("embedding service unavailable: full-text search only")
    if not data["relevant"]:
        notes.append(
            "nothing relevant found: say so and refer to the official source (INCOIS, IMD, Department of Fisheries)"
        )
    return ToolResult(
        data=data | {"lang": lang},
        source=SOURCE,
        source_url="urn:tarangyukti:kb",
        fetched_at=t_now,
        valid_at=at_t,
        confidence="high"
        if data["relevant"] and data["mode"] == "hybrid"
        else ("medium" if data["relevant"] else "low"),
        notes=notes,
    ).model_dump(mode="json")


def _confidence(data: dict[str, Any]) -> str:
    if not data["relevant"]:
        return "low"
    return "high" if data["mode"] == "hybrid" else "medium"
