from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from main import load_prompt, make_graph
from server import app


def test_ok() -> None:
    assert TestClient(app).get("/ok").json() == {"ok": True}


def test_planner_prompt_has_footer() -> None:
    assert "Advisory only — follow official INCOIS/IMD warnings." in load_prompt("planner")


async def test_graph_runs_with_fake_model_and_keeps_thread() -> None:
    # in-memory checkpointer is for this unit test only; the server uses Postgres (Milestone 5)
    model = FakeMessagesListChatModel(responses=[AIMessage(content="one"), AIMessage(content="two")])
    graph = await make_graph(checkpointer=InMemorySaver(), model=model)
    cfg = {"configurable": {"thread_id": "t1"}}
    await graph.ainvoke({"messages": [HumanMessage(content="hi")]}, cfg)
    out = await graph.ainvoke({"messages": [HumanMessage(content="again")]}, cfg)
    assert [m.content for m in out["messages"]] == ["hi", "one", "again", "two"]
