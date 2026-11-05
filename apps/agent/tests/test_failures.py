"""Replays every agent-layer row of tests/failures/failures.yaml; fails if a row was removed (ids.lock)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from main import make_graph
from src import validator
from src.gateway import FakeGateway

from .fakes import ScriptedModel

ROOT = Path(__file__).resolve().parents[3] / "tests" / "failures"
ROWS: list[dict[str, Any]] = yaml.safe_load((ROOT / "failures.yaml").read_text(encoding="utf-8"))


def test_no_row_was_removed() -> None:
    locked = {x.strip() for x in (ROOT / "ids.lock").read_text(encoding="utf-8").splitlines() if x.strip()}
    ids = [r["id"] for r in ROWS]
    assert len(ids) == len(set(ids)), "duplicate failure ids"
    assert locked <= set(ids), f"failure rows removed: {sorted(locked - set(ids))}"
    assert set(ids) <= locked, f"add new ids to tests/failures/ids.lock: {sorted(set(ids) - locked)}"


@pytest.mark.parametrize("row", [r for r in ROWS if r["layer"] == "agent"], ids=lambda r: r["id"])
async def test_failure_row(row: dict[str, Any]) -> None:
    inp, exp = row["input"], row["expect"]
    if "translation" in inp:
        from src.agents import language

        assert language.numbers_match(inp["translation"]["english"], inp["translation"]["translated"]) is exp["numbers_match"]
        return
    if "draft" in inp:
        check = validator.validate(
            inp["draft"], inp.get("citations", []), inp.get("tool_texts", []), inp.get("passages", {}), "simple"
        )
        if "ungrounded" in exp:
            assert check.ungrounded == exp["ungrounded"]
        if "quote_dropped" in exp:
            assert check.quote_dropped == exp["quote_dropped"]
        if "text" in exp:
            assert check.text == exp["text"]
        return
    # a question: the planner's LLM is down (the failure was an LLM error)
    graph = await make_graph(
        InMemorySaver(), model=ScriptedModel(fail=TimeoutError("504 DEADLINE_EXCEEDED")), gateway=FakeGateway({})
    )
    out = await graph.ainvoke(
        {"messages": [HumanMessage(content=inp["text"])]},
        {"configurable": {"thread_id": row["id"], "properties": {"lang": inp["lang"]}}},
    )
    msg = out["messages"][-1]
    assert exp["contains"] in msg.content
    assert msg.additional_kwargs["guard"]["template_fallback"] is exp["template_fallback"]
