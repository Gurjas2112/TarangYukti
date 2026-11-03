"""Knowledge-base writes (worker role, bypasses RLS). Sync psycopg: psycopg async needs a selector event loop
on Windows, and the ingest job is a batch process anyway."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from ty_common.settings import get_settings


def connect() -> psycopg.Connection[Any]:
    s = get_settings()
    if s.worker_database_url is None:
        raise RuntimeError("WORKER_DATABASE_URL is not set (run: uv run python -m ty_worker.db_roles)")
    return psycopg.connect(
        s.worker_database_url.get_secret_value(),
        options="-c search_path=public,extensions",
        connect_timeout=20,
    )


@dataclass(frozen=True)
class NewDocument:
    source_id: str
    title: str
    issuer: str
    doc_type: str
    language: str
    url: str
    licence: str
    sha256: str
    valid_from: datetime | None
    valid_to: datetime | None
    region_geojson: dict[str, Any] | None  # MultiPolygon, lon/lat
    status: str = "active"  # or "quarantined"
    quarantine_reason: str | None = None


@dataclass(frozen=True)
class NewChunk:
    ord: int
    heading_path: str | None
    content: str
    embedding: list[float]
    topics: list[str]


def sha_known(conn: psycopg.Connection[Any], sha: str) -> bool:
    return conn.execute("select 1 from kb_documents where sha256 = %s", (sha,)).fetchone() is not None


def index_version(conn: psycopg.Connection[Any]) -> int:
    row = conn.execute("select index_version from kb_index where id = 1").fetchone()
    return int(row[0]) if row else 0


def bump_index_version(conn: psycopg.Connection[Any]) -> int:
    row = conn.execute(
        "update kb_index set index_version = index_version + 1, updated_at = now() where id = 1 returning index_version"
    ).fetchone()
    assert row is not None
    return int(row[0])


def insert_document(conn: psycopg.Connection[Any], d: NewDocument, chunks: list[NewChunk], idx: int) -> str:
    """Insert a new version of `d.source_id`; older active versions become superseded by it."""
    row = conn.execute(
        "select coalesce(max(version), 0) + 1 from kb_documents where source_id = %s", (d.source_id,)
    ).fetchone()
    version = int(row[0]) if row else 1
    region = json.dumps(d.region_geojson) if d.region_geojson else None
    new = conn.execute(
        """insert into kb_documents (source_id, version, title, issuer, doc_type, language, url, licence, sha256,
               valid_from, valid_to, region, status, quarantine_reason)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   case when %s::text is null then null else st_multi(st_geomfromgeojson(%s::text))::geography end,
                   %s, %s)
           returning id""",
        (
            d.source_id,
            version,
            d.title,
            d.issuer,
            d.doc_type,
            d.language,
            d.url,
            d.licence,
            d.sha256,
            d.valid_from,
            d.valid_to,
            region,
            region,
            d.status,
            d.quarantine_reason,
        ),
    ).fetchone()
    assert new is not None
    doc_id = str(new[0])
    with conn.cursor() as cur:
        cur.executemany(
            """insert into kb_chunks (document_id, ord, heading_path, content, embedding, index_version, topics)
               values (%s, %s, %s, %s, %s::vector, %s, %s)""",
            [(doc_id, c.ord, c.heading_path, c.content, str(c.embedding), idx, c.topics) for c in chunks],
        )
    if d.status == "active":
        supersede_where(conn, "source_id = %s and status = 'active' and id <> %s", (d.source_id, doc_id), doc_id)
    return doc_id


def supersede_where(conn: psycopg.Connection[Any], where: str, params: tuple[Any, ...], new_id: str) -> int:
    """Mark matching active documents as superseded by `new_id`. Nothing is deleted."""
    cur = conn.execute(
        f"update kb_documents set status = 'superseded', superseded_by = %s, superseded_at = now() where {where}",
        (new_id, *params),
    )
    return cur.rowcount


def supersede_sources(conn: psycopg.Connection[Any], source_ids: list[str], new_id: str) -> int:
    if not source_ids:
        return 0
    return supersede_where(conn, "source_id = any(%s) and status = 'active'", (source_ids,), new_id)
