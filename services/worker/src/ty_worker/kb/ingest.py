"""kb_index pipeline (spec §6.2.1): fetch → SHA-256 skip if unchanged → convert (Docling) → sanitise
(quarantine injection-like text) → HybridChunker (≤ 512 tokens) → metadata + topics → Gemini Embedding 2
(768-d, document prefix) → upsert; older versions become superseded; bump index_version.

Sources: kb/sources/manifest.yaml (allow-listed documents and repo SOPs) and the region's live CAP bulletins
(IMD / INCOIS / SDMA alerts with validity windows; a newer alert supersedes the ones it references).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml
from shapely.geometry import box, mapping
from tarangyukti import config as mcp_config
from tarangyukti import fetch
from tarangyukti.tools import cap
from tarangyukti.tools.alert_model import Warning_
from ty_common import aliases
from ty_common.embed import doc_text, embed_sync
from ty_common.settings import find_config_dir

from . import store

log = logging.getLogger(__name__)
MAX_TOKENS = 512
MIN_CHARS, MAX_CHARS = 20, 6000


@dataclass
class Source:
    source_id: str
    title: str
    issuer: str
    doc_type: str
    language: str
    url: str
    licence: str
    format: str  # html | pdf | md | text
    file: str | None = None
    captured: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    region: dict[str, Any] | None = None  # GeoJSON MultiPolygon
    text: str | None = None  # pre-built text (bulletins): no Docling
    supersedes: list[str] = field(default_factory=list)  # source_ids this document replaces


@dataclass
class Report:
    added: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    superseded: int = 0
    index_version: int | None = None


# ── sources ─────────────────────────────────────────────────────────────────────


def _ts(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day, tzinfo=UTC)
    return datetime.fromisoformat(str(v))


def _box(b: list[float] | None) -> dict[str, Any] | None:
    if not b:
        return None
    g = mapping(box(*b))
    return {"type": "MultiPolygon", "coordinates": [g["coordinates"]]}


def manifest_sources(repo: Path) -> list[Source]:
    doc = yaml.safe_load((repo / "kb" / "sources" / "manifest.yaml").read_text(encoding="utf-8"))
    return [
        Source(
            source_id=d["source_id"],
            title=d["title"],
            issuer=d["issuer"],
            doc_type=d["doc_type"],
            language=d["language"],
            url=d["url"],
            licence=d["licence"],
            format=d["format"],
            file=d.get("file"),
            captured=d.get("captured"),
            valid_from=_ts(d.get("valid_from")),
            valid_to=_ts(d.get("valid_to")),
            region=_box(d.get("region")),
        )
        for d in doc["documents"]
    ]


def bulletin_text(w: Warning_) -> str:
    """The alert as issued (English block), with its validity, for search and verbatim quotes."""
    lines = [
        w.title,
        f"Event: {w.event or w.kind}. Issued by {w.issuer}" + (f" ({w.office})." if w.office else "."),
    ]
    if w.area_desc:
        lines.append(f"Area: {w.area_desc}.")
    lines.append(f"Valid from {w.valid_from.isoformat()} to {w.valid_to.isoformat()}.")
    if w.instruction:
        lines.append(f"Instruction: {w.instruction}")
    return "\n".join(lines)


def bulletin_source(w: Warning_) -> Source:
    area = w.area
    if area and area.get("type") == "Polygon":
        area = {"type": "MultiPolygon", "coordinates": [area["coordinates"]]}
    return Source(
        source_id=f"cap:{w.id}",
        title=f"{w.issuer} alert: {w.event or w.kind}",
        issuer=w.issuer,
        doc_type="bulletin",
        language="en-IN",
        url=w.source_url,
        licence="Official CAP alert via NDMA SACHET; credit the issuing agency",
        format="text",
        valid_from=w.valid_from,
        valid_to=w.valid_to,
        region=area,
        text=bulletin_text(w),
        supersedes=[f"cap:{r}" for r in w.references],
    )


async def live_bulletins() -> list[Source]:
    out: list[Source] = []
    for issuer in mcp_config.sources()["kb"]["live_bulletins"]:
        ws, _ = await cap.regional_warnings(issuer)
        out += [bulletin_source(w) for w in ws if not w.simulation]
    return out


# ── convert, sanitise, chunk ─────────────────────────────────────────────────────


def quarantine_reason(text: str) -> str | None:
    for pat in mcp_config.sources()["kb"]["quarantine_patterns"]:
        m = re.search(pat, text, flags=re.I)
        if m:
            return f"matched {pat!r}: {m.group(0)[:60]!r}"
    return None


def convert(src: Source, raw: bytes) -> tuple[Any, str]:
    """Docling document + its markdown text."""
    from docling.datamodel.base_models import DocumentStream
    from docling.document_converter import DocumentConverter

    ext = {"html": "html", "pdf": "pdf", "md": "md"}[src.format]
    doc = _converter(DocumentConverter).convert(DocumentStream(name=f"doc.{ext}", stream=BytesIO(raw))).document
    return doc, doc.export_to_markdown()


_CONVERTER: Any = None


def _converter(cls: Any) -> Any:
    global _CONVERTER
    if _CONVERTER is None:
        _CONVERTER = cls()
    return _CONVERTER


def chunk(doc: Any) -> list[tuple[str | None, str, str]]:
    """(heading_path, content, text_for_embedding) per chunk."""
    from docling.chunking import HybridChunker  # type: ignore[attr-defined]

    chunker = HybridChunker(max_tokens=MAX_TOKENS)  # type: ignore[call-arg]
    out = []
    for c in chunker.chunk(doc):
        content = c.text.strip()
        if not (MIN_CHARS <= len(content) <= MAX_CHARS):
            continue
        heads = getattr(c.meta, "headings", None) or []
        out.append((" > ".join(heads) or None, content, chunker.contextualize(c)))
    return out


# ── run ──────────────────────────────────────────────────────────────────────────


async def fetch_raw(src: Source, repo: Path) -> bytes:
    if src.text is not None:
        return src.text.encode("utf-8")
    if src.file:
        return (repo / src.file).read_bytes()
    if src.captured and (repo / src.captured).is_file():
        return (repo / src.captured).read_bytes()
    raw: bytes = await fetch.get_bytes(src.url, timeout=180)
    return raw


def ingest_one(conn: Any, src: Source, raw: bytes, idx: int, report: Report) -> None:
    sha = hashlib.sha256(raw).hexdigest()
    if store.sha_known(conn, sha):
        report.skipped.append(src.source_id)
        return
    if src.text is not None:
        pieces: list[tuple[str | None, str, str]] = [(None, src.text, src.text)]
        full = src.text
    else:
        doc, full = convert(src, raw)
        pieces = chunk(doc)
    if not pieces:
        report.failed.append(f"{src.source_id}: no text after conversion")
        return
    reason = quarantine_reason(full)
    vectors = embed_sync([doc_text(src.title, emb) for _, _, emb in pieces])
    chunks = [
        store.NewChunk(ord=i, heading_path=h, content=c, embedding=v, topics=aliases.find_topics(c))
        for i, ((h, c, _), v) in enumerate(zip(pieces, vectors, strict=True))
    ]
    nd = store.NewDocument(
        source_id=src.source_id,
        title=src.title,
        issuer=src.issuer,
        doc_type=src.doc_type,
        language=src.language,
        url=src.url,
        licence=src.licence,
        sha256=sha,
        valid_from=src.valid_from,
        valid_to=src.valid_to,
        region_geojson=src.region,
        status="quarantined" if reason else "active",
        quarantine_reason=reason,
    )
    doc_id = store.insert_document(conn, nd, chunks, idx)
    if reason:
        report.quarantined.append(f"{src.source_id}: {reason}")
        return
    if "cap_references" in mcp_config.sources()["kb"]["supersession"]:
        report.superseded += store.supersede_sources(conn, src.supersedes, doc_id)
    report.added.append(f"{src.source_id} ({len(chunks)} chunks)")


async def run(only: set[str] | None = None, with_bulletins: bool = True) -> Report:
    repo = find_config_dir().parent
    sources = manifest_sources(repo)
    if with_bulletins:
        try:
            sources += await live_bulletins()
        except fetch.SourceUnavailable as e:
            log.warning("live bulletins unavailable: %s", e)
    if only:
        sources = [s for s in sources if s.source_id in only]
    raws: list[tuple[Source, bytes]] = []
    report = Report()
    for s in sources:
        try:
            raws.append((s, await fetch_raw(s, repo)))
        except (fetch.SourceUnavailable, OSError) as e:
            report.failed.append(f"{s.source_id}: {e}")

    def write() -> None:
        with store.connect() as conn:
            idx = store.index_version(conn) + 1  # chunks of this run belong to the next index version
            for s, raw in raws:
                try:
                    with conn.transaction():
                        ingest_one(conn, s, raw, idx, report)
                except Exception as e:  # one bad document must not stop the run
                    log.exception("ingest failed for %s", s.source_id)
                    report.failed.append(f"{s.source_id}: {type(e).__name__}: {e}")
            if report.added or report.quarantined:
                report.index_version = store.bump_index_version(conn)
            conn.commit()

    await asyncio.to_thread(write)
    return report


def summary(r: Report) -> str:
    return json.dumps(r.__dict__, indent=1, default=str)
