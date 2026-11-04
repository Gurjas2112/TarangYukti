"""Answer records and the free-form chat kill switch (Milestone 9)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from main import make_graph, prompt_version
from src.gateway import FakeGateway
from src.records import NullRecorder

from .fakes import ScriptedModel, yukti_result


async def ask(rec: NullRecorder, model: ScriptedModel, tools: dict[str, Any], text: str, **props: Any) -> Any:
    graph = await make_graph(InMemorySaver(), model=model, gateway=FakeGateway(tools), recorder=rec)
    cfg = {"configurable": {"thread_id": "t1", "properties": props, "auth_user": {"sub": "u-1"}}}
    out = await graph.ainvoke({"messages": [HumanMessage(content=text)]}, cfg)
    return out["messages"][-1]


async def test_every_answer_is_recorded_with_versions() -> None:
    rec = NullRecorder()
    msg = await ask(
        rec,
        ScriptedModel(fail=RuntimeError("no LLM")),
        {"yukti_evaluate": yukti_result("NO-GO")},
        "Today's sea",
        intent="todays_sea",
    )
    assert len(rec.rows) == 1
    row = rec.rows[0]
    assert row["thread_id"] == "t1" and row["user_id"] == "u-1" and row["verdict"] == "NO-GO"
    assert row["reply"] == msg.content and row["question"] == "Today's sea"
    assert row["prompt_version"] == prompt_version() and len(row["config_version"]) >= 12 and row["model"]
    assert row["fallback"] == "button" and "template_fallback" in row["guard"]


async def test_chat_off_pauses_free_form_but_not_buttons() -> None:
    rec = NullRecorder(chat_off=True)
    never = ScriptedModel(fail=RuntimeError("the LLM must not be called while chat is off"))
    msg = await ask(rec, never, {}, "What does the law say?")
    assert msg.content.startswith("Questions are paused") and msg.content.rstrip().endswith("IMD warnings.")
    assert rec.rows[-1]["fallback"] == "chat_off" and not never.seen

    msg = await ask(rec, never, {"yukti_evaluate": yukti_result("GO")}, "Today's sea", intent="todays_sea")
    assert msg.content.startswith("Good to go.")
