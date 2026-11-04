"""The agent graph end to end, offline: scripted model + fake tools + in-memory checkpointer (tests only)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from main import make_graph
from src.gateway import FakeGateway

from .fakes import ScriptedModel, answer, call, fence_result, kb_result, yukti_result

FOOTER = "Advisory only — follow official INCOIS/IMD warnings."


async def ask(model: ScriptedModel, tools: dict[str, Any], text: str, thread: str = "t", **props: Any) -> Any:
    graph = await make_graph(InMemorySaver(), model=model, gateway=FakeGateway(tools))
    out = await graph.ainvoke(
        {"messages": [HumanMessage(content=text)]}, {"configurable": {"thread_id": thread, "properties": props}}
    )
    return out, out["messages"][-1]


async def test_grounded_answer_passes() -> None:
    m = ScriptedModel(
        script=[call("geospatial", {}), answer("From Rameswaram harbour the border line is 22.8 km away.")]
    )
    out, msg = await ask(m, {"fence_check": fence_result()}, "How far is the border?")
    assert "22.8 km" in msg.content and msg.content.endswith(FOOTER)
    assert msg.additional_kwargs["guard"]["ungrounded_number"] == 0


async def test_invented_number_rewritten_then_template() -> None:
    m = ScriptedModel(
        script=[
            call("geospatial", {}),
            answer("The border line is 12.5 km away."),
            answer("The border line is 13 km away."),  # the rewrite also invents a number
        ]
    )
    out, msg = await ask(m, {"fence_check": fence_result()}, "How far is the border?")
    assert "12.5" not in msg.content and "13 km" not in msg.content
    assert "could not check this answer" in msg.content
    assert msg.additional_kwargs["guard"]["template_fallback"] is True


async def test_rewrite_fixes_the_draft() -> None:
    m = ScriptedModel(
        script=[
            call("geospatial", {}),
            answer("The border line is 12.5 km away."),
            answer("The border line is 22.8 km away."),
        ]
    )
    out, msg = await ask(m, {"fence_check": fence_result()}, "How far is the border?")
    assert "22.8 km" in msg.content
    assert msg.additional_kwargs["guard"]["rewritten"] is True


async def test_simple_mode_verdict_from_phrases_not_llm() -> None:
    m = ScriptedModel(script=[call("yukti", {}), answer("It looks fine, go fishing!", answer_id="ans-123")])
    out, msg = await ask(m, {"yukti_evaluate": yukti_result("NO-GO")}, "Can I go to sea tomorrow morning?")
    assert msg.content.startswith("Don't go today.")
    assert "There is an official INCOIS warning" in msg.content
    assert "go fishing" not in msg.content  # the LLM text never replaces the verdict in Simple mode
    assert out["answer_id"] == "ans-123"


async def test_llm_down_free_form_says_needs_network() -> None:
    m = ScriptedModel(fail=TimeoutError("504 DEADLINE_EXCEEDED"))
    out, msg = await ask(m, {}, "What does the law say?")
    assert msg.content.startswith("I need the internet")
    assert msg.additional_kwargs["guard"]["template_fallback"] is True


async def test_button_flow_needs_no_llm() -> None:
    m = ScriptedModel(fail=RuntimeError("no LLM should be called"))
    out, msg = await ask(m, {"yukti_evaluate": yukti_result("NO-GO")}, "Today's sea", intent="todays_sea")
    assert msg.content.startswith("Don't go today. Next good time: 06:30 on 4 Nov (IST).")
    assert not m.seen


async def test_citation_must_be_verbatim() -> None:
    chunk = "The mechanised fishing vessel shall leave the notified place of berthing only after 5 am."
    good = ScriptedModel(
        script=[
            call("knowledge", {"question": "q"}),
            answer(
                "Mechanised boats may leave only after 5 am [K1].",
                citations=[{"marker": "K1", "quote": "leave the notified place of berthing only after 5 am"}],
            ),
        ]
    )
    out, msg = await ask(good, {"kb_search": kb_result(chunk)}, "When may mechanised boats leave?")
    assert "[K1]" in msg.content and msg.additional_kwargs["citations"][0]["marker"] == "K1"
    card = out["citations"][0]
    assert card["marker"] == "K1" and card["quote"].startswith("leave the notified") and card["issuer"]

    bad = ScriptedModel(
        script=[
            call("knowledge", {"question": "q"}),
            answer(
                "Mechanised boats may leave only after 5 am [K1].",
                citations=[{"marker": "K1", "quote": "boats may go out after five in the morning"}],
            ),
        ]
    )
    _, msg2 = await ask(bad, {"kb_search": kb_result(chunk)}, "When may mechanised boats leave?")
    assert "[K1]" not in msg2.content


async def test_thread_memory_keeps_language_and_history() -> None:
    m = ScriptedModel(
        script=[
            call("geospatial", {}),
            answer("The border line is 22.8 km away."),
            call("geospatial", {}, 1),
            answer("Still 22.8 km.", i=10),
        ]
    )
    graph = await make_graph(InMemorySaver(), model=m, gateway=FakeGateway({"fence_check": fence_result()}))
    cfg = {"configurable": {"thread_id": "mem", "properties": {"lang": "en-IN"}}}
    await graph.ainvoke({"messages": [HumanMessage(content="How far is the border?")]}, cfg)
    out = await graph.ainvoke(
        {"messages": [HumanMessage(content="And now?")]}, {"configurable": {"thread_id": "mem", "properties": {}}}
    )
    assert out["lang"] == "en-IN"
    humans = [x.content for x in out["messages"] if isinstance(x, HumanMessage)]
    assert humans == ["How far is the border?", "And now?"]
    assert "digests" in out and out["digests"] == []  # per-turn working data is not kept
    assert all("lat" not in str(v) for k, v in out.items() if k in ("last_cell", "evidence"))


async def test_out_of_region_tool_error_is_reported_not_invented() -> None:
    m = ScriptedModel(script=[call("weather_intel", {}), answer("Wave data is not available right now.")])
    _, msg = await ask(m, {}, "How are the waves?")
    assert "not available" in msg.content


async def test_mission_control_and_map_actions_in_expert_mode() -> None:
    m = ScriptedModel(fail=RuntimeError("no LLM should be called"))
    out, _ = await ask(m, {"yukti_evaluate": yukti_result("NO-GO")}, "Today's sea", intent="todays_sea", mode="expert")
    assert out["mission"][0] == "language" and "yukti" in out["mission"] and out["mission"][-1] == "explain"
    tools = [a["tool"] for a in out["ui_actions"]]
    assert tools[0] == "flyTo" and out["ui_actions"][0]["args"]["zoom"] == 9
    assert ("openLedger" in tools) == bool(out["answer_id"])


async def test_simple_mode_never_opens_the_ledger() -> None:
    m = ScriptedModel(fail=RuntimeError("no LLM should be called"))
    out, _ = await ask(m, {"yukti_evaluate": yukti_result("GO")}, "Today's sea", intent="todays_sea", mode="simple")
    assert [a["tool"] for a in out["ui_actions"]] == ["flyTo"]


async def test_no_verdict_no_map_actions() -> None:
    m = ScriptedModel(fail=TimeoutError("504"))
    out, _ = await ask(m, {}, "What does the law say?")
    assert out["ui_actions"] == [] and out["mission"][:2] == ["language", "planner"]
