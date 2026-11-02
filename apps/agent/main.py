"""TarangYukti agent graph.

Milestone 1: a single planner on Gemini with no tools, so the AG-UI wiring can be exercised end to end.
Milestone 5 replaces it with the planner + eight specialists wrapped as tools, and the validator node.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langgraph.types import Checkpointer
from ty_common.settings import get_settings

PROMPTS = Path(__file__).parent / "src" / "prompts"


def load_prompt(name: str) -> str:
    """Prompts live in files, never inline (prompt §17)."""
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def make_model() -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    s = get_settings()
    key = s.google_api_key.get_secret_value() if s.google_api_key else None
    return ChatGoogleGenerativeAI(
        model=s.orca_model, temperature=0, google_api_key=key, timeout=s.llm_timeout_s
    )


async def make_graph(checkpointer: Checkpointer = None, model: BaseChatModel | None = None) -> Any:
    """Build the compiled graph. The server passes an AsyncPostgresSaver (Milestone 5)."""
    return create_agent(
        model=model or make_model(),
        tools=[],
        system_prompt=load_prompt("planner"),
        checkpointer=checkpointer,
    )
