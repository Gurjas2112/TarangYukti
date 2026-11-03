"""kb_search pieces that need no database: RRF merge, full-text query, relevance and fallbacks."""

from __future__ import annotations

from typing import Any

import pytest

from tarangyukti.rag import search


def test_rrf_merge_rewards_agreement() -> None:
    a = [{"chunk_id": 1, "sim": 0.7}, {"chunk_id": 2, "sim": 0.6}, {"chunk_id": 3, "sim": 0.5}]
    b = [{"chunk_id": 3, "sim": 0.8}, {"chunk_id": 1, "sim": 0.65}]
    hits = search.rrf_merge([a, b])
    assert [h.chunk_id for h in hits] == [1, 3, 2]  # 1 and 3 appear in both lists
    assert hits[1].sim == 0.8  # best similarity across the two queries is kept


def test_rrf_merge_top_n_and_fulltext_only() -> None:
    rows = [{"chunk_id": i, "sim": None} for i in range(20)]
    hits = search.rrf_merge([rows])
    assert len(hits) == search.TOP_N
    assert all(h.sim is None for h in hits)


def test_fts_query_is_an_or_of_words() -> None:
    q = search.fts_query("When is the fishing ban on the east coast?")
    assert q == "fishing or ban or east or coast"
    assert "மீன்பிடி" in search.fts_query("மீன்பிடி தடை எப்போது?")


async def test_relevance_threshold_and_fulltext_path(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_db(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if "kb_hybrid_search" in sql:
            return [{"chunk_id": 7, "score": 0.02, "sim": 0.4 if params and params["q_emb"] else None}]
        return [
            {
                "chunk_id": 7,
                "content": "Text",
                "heading_path": None,
                "topics": [],
                "document_id": "d",
                "source_id": "s",
                "version": 1,
                "title": "T",
                "issuer": "DoF",
                "doc_type": "order",
                "language": "en-IN",
                "url": "u",
                "licence": "l",
                "valid_from": None,
                "valid_to": None,
                "ingested_at": search.now(),
            }
        ]

    async def emb_ok(text: str) -> list[float]:
        return [0.0] * 768

    async def emb_down(text: str) -> None:
        return None

    async def no_rewrite(q: str) -> None:
        return None

    async def idx() -> int:
        return 1

    monkeypatch.setattr(search, "db", fake_db)
    monkeypatch.setattr(search, "rewrite_english", no_rewrite)
    monkeypatch.setattr(search, "index_version", idx)
    monkeypatch.setattr(search, "_embed", emb_ok)
    r = await search.kb_search("ban dates")
    assert r["data"]["mode"] == "hybrid" and r["data"]["relevant"] is False  # 0.4 < RAG_MIN_SIM 0.55
    assert r["confidence"] == "low" and any("nothing relevant" in n for n in r["notes"])
    assert r["data"]["chunks"][0]["marker"] == "K1"

    monkeypatch.setattr(search, "_embed", emb_down)
    r2 = await search.kb_search("ban dates again")
    assert r2["data"]["mode"] == "full_text" and r2["data"]["relevant"] is True
    assert any("full-text search only" in n for n in r2["notes"])


async def test_database_down_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def down() -> int:
        raise search.SearchUnavailable("knowledge base unavailable: OperationalError")

    monkeypatch.setattr(search, "index_version", down)
    r = await search.kb_search("anything")
    assert r["data"]["available"] is False


async def test_input_validation() -> None:
    from tarangyukti import qc

    with pytest.raises(ValueError):
        await search.kb_search("   ")
    with pytest.raises(ValueError, match="timezone"):
        await search.kb_search("ban", at="2026-11-03T04:00:00")
    with pytest.raises(qc.OutOfRegion):
        await search.kb_search("ban", near_lat=13.08, near_lon=80.27)
