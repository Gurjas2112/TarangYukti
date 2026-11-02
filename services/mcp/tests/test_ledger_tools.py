"""Constraint Ledger (locked schema, bi-temporal, no personal data) and the yukti_evaluate / route_safest tools."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from tarangyukti import ledger
from tarangyukti.yukti import engine

from .conftest import NOW, make_snapshot
from .yukti_helpers import HARBOUR, T0, make_ctx, warning


def test_schema_is_locked() -> None:
    assert ledger.LEDGER_LABELS == {"Answer", "ConstraintResult", "Observation", "Dataset", "Chunk"}
    assert ledger.LEDGER_RELS == {"CHECKED", "BASED_ON", "FROM", "CITES"}
    ledger.check_schema(ledger.WRITE_ANSWER)
    with pytest.raises(ledger.LedgerSchemaError):
        ledger.check_schema("MERGE (u:User {id: $id})")
    with pytest.raises(ledger.LedgerSchemaError):
        ledger.check_schema("MATCH (a:Answer) MERGE (a)-[:KNOWS]->(b:Answer)")


def test_replay_is_time_guarded() -> None:
    assert "o.known_at <= a.at" in ledger.REPLAY


def _params() -> dict[str, Any]:
    ctx = make_ctx(warnings=[warning(T0, 12, wid="INCOIS-1")])
    ev = engine.evaluate(ctx, engine.candidate(ctx, HARBOUR, None, T0))
    return ledger.build_params(ctx, ev, "ans-1", "thread-hash", "ta-IN", "cfg", "layer")


def test_params_are_bitemporal() -> None:
    p = _params()
    assert p["answer"]["verdict"] == "NO-GO"
    obs = [o for r in p["results"] for o in r["observations"]]
    assert obs and all(o["known_at"] is not None and o["valid_at"] is not None for o in obs)
    keys = [o["key"] for o in obs]
    assert len(keys) == len(set(keys)) and all(k.startswith("ans-1:") for k in keys)  # never overwritten
    h1 = next(r for r in p["results"] if r["id"] == "H1")
    assert h1["ok"] is False and h1["observations"][0]["dataset"] == "INCOIS alert INCOIS-1"


def test_no_location_in_ledger() -> None:
    p = _params()
    assert "start_cell" not in p["answer"] and "goal_cell" not in p["answer"]
    blob = json.dumps(p, default=str)
    assert "9.288" not in blob and "79.313" not in blob
    assert HARBOUR not in json.dumps(p["answer"], default=str)


class FakeSession:
    def __init__(self, log: list[tuple[str, dict[str, Any]]]) -> None:
        self.log = log

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def run(self, query: str, params: dict[str, Any]) -> None:
        self.log.append((query, params))


class FakeDriver:
    def __init__(self) -> None:
        self.log: list[tuple[str, dict[str, Any]]] = []

    def session(self, database: str) -> FakeSession:
        return FakeSession(self.log)


async def test_write_uses_the_fixed_statement() -> None:
    d = FakeDriver()
    assert await ledger.write(_params(), d)
    ((query, params),) = d.log
    assert query == ledger.WRITE_ANSWER
    assert params["answer"]["id"] == "ans-1"


async def test_write_skipped_without_neo4j() -> None:
    assert await ledger.write(_params()) is False  # conftest clears NEO4J_PASSWORD


async def test_write_failure_does_not_raise() -> None:
    class Broken(FakeDriver):
        def session(self, database: str) -> FakeSession:
            raise ConnectionError("down")

    assert await ledger.write(_params(), Broken()) is False


# ── tools, offline (snapshot mode) ───────────────────────────────────────────────


async def test_yukti_evaluate_snapshot_mode(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ty_common.settings import get_settings

    from tarangyukti.tools import yukti_tools

    make_snapshot(env)  # INCOIS alert for Ramanathapuram 00:00–12:00 UTC; no SDMA file
    monkeypatch.setattr(get_settings(), "data_mode", "snapshot")
    r = await yukti_tools.yukti_evaluate("small_frp", 9.288, 79.313)
    d = r["data"]
    assert d["verdict"] == "NO-GO"
    assert d["as_of"] == (NOW - timedelta(hours=1)).isoformat()  # the snapshot's capture time
    failed = d["requested"]["failed_hard"]
    assert "H1" in failed  # the INCOIS alert covers Ramanathapuram
    assert "H8" in failed  # SDMA alerts missing from this snapshot → never GO
    assert r["confidence"] == "low"
    assert d["answer_id"] is None  # no Neo4j in tests
    assert any(e["id"] == "H1" and "INCOIS" in e["detail"] for e in d["requested"]["ledger"])


async def test_yukti_evaluate_rejects_bad_input(env: Path) -> None:
    from tarangyukti import qc
    from tarangyukti.tools import yukti_tools

    with pytest.raises(qc.OutOfRegion):
        await yukti_tools.yukti_evaluate("small_frp", 13.08, 80.27)
    make_snapshot(env)
    with pytest.raises(ValueError, match="unknown boat type"):
        await yukti_tools.yukti_evaluate("yacht", 9.288, 79.313)
    with pytest.raises(ValueError, match="timezone"):
        await yukti_tools.yukti_evaluate("small_frp", 9.288, 79.313, depart_at="2026-11-03T04:00:00")


async def test_route_safest_snapshot_mode(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ty_common.settings import get_settings

    from tarangyukti.tools import yukti_tools

    make_snapshot(env)
    monkeypatch.setattr(get_settings(), "data_mode", "snapshot")
    # 9.20 N 79.40 E: open Gulf of Mannar about 15 km from the border line; leave when the forecast starts
    r = await yukti_tools.route_safest("small_frp", 9.288, 79.313, 9.20, 79.40, depart_at=NOW.isoformat())
    d = r["data"]
    assert d["found"] is True
    assert d["cells"][0] == HARBOUR and len(d["cells"]) == len(d["times"])
    beyond = await yukti_tools.route_safest("small_frp", 9.288, 79.313, 9.45, 79.48)
    assert beyond["data"]["found"] is False
