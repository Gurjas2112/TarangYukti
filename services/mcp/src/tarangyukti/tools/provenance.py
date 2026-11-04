"""answer_ledger: replay a stored answer's Constraint Ledger (spec §10.3 Replay, §13 provenance)."""

from __future__ import annotations

import uuid
from typing import Any

from ty_common.models import ToolResult

from .. import ledger
from .common import now, unavailable


async def answer_ledger(answer_id: str) -> dict[str, Any]:
    """The Constraint Ledger of a past answer as it was known then: the verdict, each H1–H8 / S1–S5 result with
    its observations (valid_at = when the value is true, known_at = when it was fetched; only observations known
    by the answer time), and the cited passages. answer_id is the Yukti answer id (UUID)."""
    try:
        uuid.UUID(answer_id)
    except ValueError:
        return unavailable("Constraint Ledger (Neo4j)", "urn:tarangyukti:ledger", "not an answer id")
    data = await ledger.read(answer_id)
    if not data:
        return unavailable("Constraint Ledger (Neo4j)", "urn:tarangyukti:ledger", "no ledger for this answer")
    data["results"] = [r for r in data["results"] if r]
    data["citations"] = [c for c in data["citations"] if c]
    for r in data["results"]:
        r["observations"] = [o for o in r["observations"] if o]
    return ToolResult(
        data=data,
        source="Constraint Ledger (Neo4j)",
        source_url="urn:tarangyukti:ledger",
        fetched_at=now(),
        confidence="high",
    ).model_dump(mode="json")
