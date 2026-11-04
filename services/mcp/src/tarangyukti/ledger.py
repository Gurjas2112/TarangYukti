"""Constraint Ledger in Neo4j (prompt §6, spec §6.1.5).

    (:Answer)-[:CHECKED]->(:ConstraintResult)-[:BASED_ON]->(:Observation)-[:FROM]->(:Dataset)
    (:Answer)-[:CITES {quote}]->(:Chunk {id, version})          (Milestone 4)

The schema is locked: only LEDGER_LABELS and LEDGER_RELS may appear in Cypher, checked before every
write. No LLM ever writes Cypher — these statements are fixed strings with parameters. Observations keep
`valid_at` (when the value is true) and `known_at` (when it was fetched) and are never overwritten (keys
are unique per answer), so a past answer replays with `WHERE o.known_at <= a.at`. Only pseudonymous
thread ids are stored: no names, phones, coordinates or the user's cells.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any

from ty_common.settings import get_settings

from .yukti.model import Ctx, Evaluation

log = logging.getLogger(__name__)

LEDGER_LABELS = frozenset({"Answer", "ConstraintResult", "Observation", "Dataset", "Chunk"})
LEDGER_RELS = frozenset({"CHECKED", "BASED_ON", "FROM", "CITES"})


class LedgerSchemaError(ValueError):
    pass


def check_schema(cypher: str) -> str:
    """Refuse any statement that uses a label or relationship type outside the locked schema."""
    labels = set(re.findall(r"\(\s*\w*\s*:\s*(\w+)", cypher))
    rels = set(re.findall(r"\[\s*\w*\s*:\s*(\w+)", cypher))
    bad = (labels - LEDGER_LABELS) | (rels - LEDGER_RELS)
    if bad:
        raise LedgerSchemaError(f"not in the locked ledger schema: {sorted(bad)}")
    return cypher


WRITE_ANSWER = check_schema(
    """
MERGE (a:Answer {id: $answer.id})
SET a.at = $answer.at, a.kind = $answer.kind, a.verdict = $answer.verdict, a.lang = $answer.lang,
    a.thread = $answer.thread, a.config_version = $answer.config_version, a.boat_type = $answer.boat_type,
    a.depart = $answer.depart
WITH a
UNWIND $results AS r
MERGE (c:ConstraintResult {key: r.key})
SET c.id = r.id, c.kind = r.kind, c.ok = r.ok, c.value = r.value, c.unit = r.unit, c.detail = r.detail,
    c.unknown = r.unknown
MERGE (a)-[:CHECKED]->(c)
WITH c, r
UNWIND r.observations AS o
MERGE (ob:Observation {key: o.key})
SET ob.var = o.var, ob.value = o.value, ob.valid_at = o.valid_at, ob.known_at = o.known_at
MERGE (c)-[:BASED_ON]->(ob)
MERGE (d:Dataset {name: o.dataset, version: o.version})
SET d.url = o.url
MERGE (ob)-[:FROM]->(d)
"""
)

REPLAY = check_schema(
    """
MATCH (a:Answer {id: $answer_id})-[:CHECKED]->(c:ConstraintResult)-[:BASED_ON]->(o:Observation)-[:FROM]->(d:Dataset)
WHERE o.known_at <= a.at
RETURN c.id AS id, c.ok AS ok, c.value AS value, o.var AS var, o.valid_at AS valid_at,
       o.known_at AS known_at, d.name AS dataset, d.version AS version
ORDER BY c.id
"""
)


def _value(v: object) -> object:
    return v if isinstance(v, (int, float, str, bool)) or v is None else str(v)


def build_params(
    ctx: Ctx,
    ev: Evaluation,
    answer_id: str,
    thread: str | None,
    lang: str | None,
    config_version: str,
    layer_version: str,
) -> dict[str, Any]:
    inputs = {i.name: i for i in ctx.inputs}
    warn_by_id = {w.id: w for w in ctx.warnings}
    results = []
    for n, e in enumerate(ev.ledger):
        obs = []
        for k, ref in enumerate(e.evidence):
            key = f"{answer_id}:{n}:{k}"
            valid_at: datetime = e.at or ctx.as_of
            if ref in inputs:
                i = inputs[ref]
                obs.append(
                    {
                        "key": key,
                        "var": f"{e.id}:{ref}",
                        "value": _value(e.value),
                        "valid_at": valid_at,
                        "known_at": i.fetched_at,
                        "dataset": i.source,
                        "version": i.fetched_at.isoformat(),
                        "url": i.source_url,
                    }
                )
            elif ref in warn_by_id:
                w = warn_by_id[ref]
                src = next((i for i in ctx.inputs if i.name == f"warnings_{w.issuer.lower()}"), None)
                obs.append(
                    {
                        "key": key,
                        "var": f"{e.id}:alert",
                        "value": w.title,
                        "valid_at": w.valid_from,
                        "known_at": src.fetched_at if src else ctx.as_of,
                        "dataset": f"{w.issuer} alert {w.id}",
                        "version": w.issued_at.isoformat(),
                        "url": w.source_url,
                    }
                )
            else:  # layers, config, computed values
                obs.append(
                    {
                        "key": key,
                        "var": f"{e.id}:{ref}",
                        "value": _value(e.value),
                        "valid_at": valid_at,
                        "known_at": ctx.as_of,
                        "dataset": ref,
                        "version": layer_version if ref.startswith("layer:") else config_version,
                        "url": None,
                    }
                )
        results.append(
            {
                "key": f"{answer_id}:{n}",
                "id": e.id,
                "kind": e.kind,
                "ok": e.ok,
                "value": _value(e.value),
                "unit": e.unit,
                "detail": e.detail,
                "unknown": e.unknown,
                "observations": obs,
            }
        )
    c = ev.candidate
    answer = {
        "id": answer_id,
        "at": ctx.as_of,
        "kind": "trip",
        "verdict": ev.outcome,
        "lang": lang,
        "thread": thread,
        "config_version": config_version,
        "boat_type": ctx.boat_type,
        "depart": c.depart,
    }
    return {"answer": answer, "results": results}


def new_answer_id() -> str:
    return str(uuid.uuid4())


async def write(params: dict[str, Any], driver: Any | None = None) -> bool:
    """Write one answer's ledger. Returns False (and logs) if Neo4j is not configured or unreachable —
    the verdict itself never depends on the ledger write."""
    own = driver is None
    if driver is None:
        s = get_settings()
        if s.neo4j_password is None:
            return False
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_username, s.neo4j_password.get_secret_value()))
    assert driver is not None
    try:
        async with driver.session(database=get_settings().neo4j_database) as session:
            await session.run(WRITE_ANSWER, params)
        return True
    except Exception as e:  # ledger is evidence storage; a write failure must not hide the verdict
        log.warning("ledger write failed: %s", type(e).__name__)
        return False
    finally:
        if own:
            await driver.close()


async def replay(answer_id: str, driver: Any) -> list[dict[str, Any]]:
    async with driver.session(database=get_settings().neo4j_database) as session:
        result = await session.run(REPLAY, {"answer_id": answer_id})
        return [dict(r) async for r in result]


READ_ANSWER = check_schema(
    """
MATCH (a:Answer {id: $answer_id})
OPTIONAL MATCH (a)-[:CHECKED]->(c:ConstraintResult)
OPTIONAL MATCH (c)-[:BASED_ON]->(o:Observation)-[:FROM]->(d:Dataset)
WHERE o.known_at <= a.at
WITH a, c, collect(CASE WHEN o IS NULL THEN NULL ELSE {var: o.var, value: o.value, valid_at: toString(o.valid_at),
     known_at: toString(o.known_at), dataset: d.name, version: d.version, url: d.url} END) AS obs
ORDER BY c.id
WITH a, collect(CASE WHEN c IS NULL THEN NULL ELSE {id: c.id, kind: c.kind, ok: c.ok, value: c.value, unit: c.unit,
     detail: c.detail, unknown: c.unknown, observations: obs} END) AS results
OPTIONAL MATCH (a)-[q:CITES]->(k:Chunk)
RETURN a {.id, at: toString(a.at), .kind, .verdict, .lang, .config_version, .boat_type, depart: toString(a.depart)}
       AS answer, results, collect(CASE WHEN k IS NULL THEN NULL ELSE {chunk_id: k.id, version: k.version,
       quote: q.quote} END) AS citations
"""
)


async def read(answer_id: str, driver: Any | None = None) -> dict[str, Any] | None:
    """One answer's full ledger as it was known when the answer was given (observations with known_at ≤ a.at)."""
    own = driver is None
    if driver is None:
        s = get_settings()
        if s.neo4j_password is None:
            return None
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            s.neo4j_uri,
            auth=(s.neo4j_username, s.neo4j_password.get_secret_value()),
            notifications_min_severity="OFF",  # CITES/Chunk may not exist yet: not an error
        )
    assert driver is not None
    try:
        async with driver.session(database=get_settings().neo4j_database) as session:
            rec = await (await session.run(READ_ANSWER, {"answer_id": answer_id})).single()
        return dict(rec) if rec else None
    finally:
        if own:
            await driver.close()


PURGE = check_schema(
    """
MATCH (a:Answer) WHERE a.at < datetime() - duration({days: $days})
OPTIONAL MATCH (a)-[:CHECKED]->(c:ConstraintResult)
OPTIONAL MATCH (c)-[:BASED_ON]->(o:Observation)
WITH a, collect(DISTINCT c) AS cs, collect(DISTINCT o) AS os
FOREACH (x IN os | DETACH DELETE x)
FOREACH (x IN cs | DETACH DELETE x)
DETACH DELETE a
RETURN count(*) AS answers
"""
)


async def purge(days: int = 180) -> int:
    """Delete answers (and their results and observations) older than `days` — retention (spec §8.5).
    Datasets and passages are shared and stay."""
    s = get_settings()
    if s.neo4j_password is None:
        return 0
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        s.neo4j_uri, auth=(s.neo4j_username, s.neo4j_password.get_secret_value()), notifications_min_severity="OFF"
    )
    try:
        async with driver.session(database=s.neo4j_database) as session:
            rec = await (await session.run(PURGE, {"days": days})).single()
        return int(rec["answers"]) if rec else 0
    finally:
        await driver.close()
