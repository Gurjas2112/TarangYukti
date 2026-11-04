"""Offline doubles: a scripted tool-calling chat model and canned tool results."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable


class ScriptedModel(BaseChatModel):
    """Returns the scripted AIMessages in order (tool calls included). Raises if `fail` is set."""

    script: list[AIMessage] = []
    fail: Exception | None = None
    seen: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable[Any, BaseMessage]:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.seen.append(messages)
        if self.fail:
            raise self.fail
        msg = self.script.pop(0) if self.script else AIMessage(content="")
        return ChatResult(generations=[ChatGeneration(message=msg)])


def call(name: str, args: dict[str, Any], i: int = 0) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{i}-{name}"}])


def answer(
    text: str, citations: list[dict[str, str]] | None = None, answer_id: str | None = None, i: int = 9
) -> AIMessage:
    return call("Answer", {"text": text, "citations": citations or [], "answer_id": answer_id}, i)


def yukti_result(verdict: str = "NO-GO") -> dict[str, Any]:
    failed = (
        [
            {
                "id": "H1",
                "kind": "hard",
                "name": "Official warning active",
                "ok": False,
                "value": "High wave alert for Ramanathapuram",
                "unit": None,
                "detail": "INCOIS high_wave until 2026-11-04T00:30:00+00:00",
                "at": "2026-11-03T23:00:00+00:00",
                "unknown": False,
            }
        ]
        if verdict == "NO-GO"
        else []
    )
    ev = {
        "outcome": verdict,
        "feasible": verdict != "NO-GO",
        "failed_hard": [f["id"] for f in failed],
        "risk": 0.42,
        "score": 1.0,
        "depart": "2026-11-03T23:00:00+00:00",
        "return_at": "2026-11-04T07:00:00+00:00",
        "route_km": 20.0,
        "route_cells": [],
        "local_area_cells": 60,
        "notes": [],
        "ledger": failed,
    }
    earliest = dict(ev, outcome="GO", depart="2026-11-04T01:00:00+00:00", ledger=[])
    return {
        "data": {
            "verdict": verdict,
            "boat_type": "small_frp",
            "as_of": "2026-11-03T22:50:00+00:00",
            "requested": ev,
            "earliest_window": earliest,
            "recommended": earliest,
            "checked_departures": 49,
            "answer_id": "ans-123",
        },
        "source": "Yukti",
        "source_url": "urn:x",
        "fetched_at": "2026-11-03T22:50:00+00:00",
        "cache": "miss",
        "confidence": "high",
        "notes": [],
    }


def fence_result() -> dict[str, Any]:
    return {
        "data": {"imbl_km": 22.8, "side": "india", "ring": "clear", "in_mpa": False, "mpa_name": None, "cell": "x"},
        "source": "IMBL",
        "source_url": "urn:x",
        "fetched_at": "2026-11-03T22:50:00+00:00",
        "cache": "miss",
        "confidence": "high",
        "notes": [],
    }


def kb_result(content: str) -> dict[str, Any]:
    return {
        "data": {
            "relevant": True,
            "mode": "hybrid",
            "chunks": [
                {
                    "marker": "K1",
                    "content": content,
                    "document": {"issuer": "GoTN", "title": "TN Act", "valid_to": None},
                }
            ],
        },
        "source": "kb",
        "source_url": "urn:kb",
        "fetched_at": "2026-11-03T22:50:00+00:00",
        "cache": "miss",
        "confidence": "high",
        "notes": [],
    }


ToolMap = dict[str, dict[str, Any] | Callable[[dict[str, Any]], Any]]


def iter_tool_calls(model: ScriptedModel) -> Iterator[str]:
    for msgs in model.seen:
        for m in msgs:
            for tc in getattr(m, "tool_calls", []) or []:
                yield tc["name"]
