"""TarangYukti agent graph (prompt §9, spec §6.4).

    prepare ──► button (app buttons: deterministic, no LLM) ───────────────┐
        └────► planner (Gemini + 7 specialist tools) ─► validate ◄─┐       ▼
                                                        │    rewrite (once)  finalize ─► END
                                                        └──────────────────────┘
prepare     — Language agent: pick and keep the reply language; read mode / intent / boat from the app.
planner     — create_agent with the specialists wrapped as tools; returns a structured Answer (English).
validate    — numbers grounded, citations verbatim, no codes in Simple mode, never "safe"; one rewrite, then
              the template from the ledger.
finalize    — Simple mode with a verdict: approved-phrase template; free text: Sarvam translation with the
              number check; footer; guardrail record.
LLM down (timeout or API error): button flows answer from the ledger template; free-form questions get the
"needs the network" phrase.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Checkpointer
from pydantic import BaseModel, Field
from ty_common.settings import get_settings
from ty_common.telemetry import record_guardrails

from src import templates, validator
from src.agents import language
from src.agents.base import Evidence, Turn, prompt
from src.agents.specialists import make_tools
from src.gateway import Gateway, MCPGateway

log = logging.getLogger(__name__)
PROMPTS = Path(__file__).parent / "src" / "prompts"
BUTTONS = {"todays_sea"}  # Milestone 6 adds the other buttons
MAX_TOOL_CALLS = 8


def load_prompt(name: str) -> str:
    """Prompts live in files, never inline (prompt §17)."""
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def prompt_version() -> str:
    h = hashlib.sha256()
    for f in sorted(PROMPTS.glob("*.md")):
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


class Citation(BaseModel):
    marker: str = Field(description="A passage marker from the knowledge tool, e.g. K2")
    quote: str = Field(description="Words copied exactly from that passage, at least 12 characters")


class Answer(BaseModel):
    """The final answer: English text, the citations it uses, and the Yukti answer_id if a verdict is reported."""

    text: str = Field(description="The answer in English, 2-5 short sentences, [Kn] markers where documents are used")
    citations: list[Citation] = Field(default_factory=list)
    answer_id: str | None = None


class OrcaState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    lang: NotRequired[str]
    mode: NotRequired[Literal["simple", "expert"]]
    user_id: NotRequired[str | None]
    boat_profile: NotRequired[str]
    home_harbour: NotRequired[str]
    last_cell: NotRequired[str | None]  # H3 cell only, never lat/lon
    intent: NotRequired[str | None]  # app button for this turn
    answer_id: NotRequired[str | None]
    evidence: NotRequired[list[str]]  # ids of the evidence of the last answer (answer ids, passage markers)
    # per-turn working fields (cleared by finalize)
    digests: NotRequired[list[dict[str, Any]]]
    passages: NotRequired[dict[str, str]]
    draft: NotRequired[dict[str, Any] | None]
    rewritten: NotRequired[bool]
    fallback: NotRequired[str | None]
    guard: NotRequired[dict[str, Any]]


def make_model(effort: Literal["low", "medium", "high"]) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    s = get_settings()
    key = s.google_api_key.get_secret_value() if s.google_api_key else None
    return ChatGoogleGenerativeAI(
        model=s.orca_model,
        temperature=0,
        google_api_key=key,
        timeout=s.llm_timeout_s,
        max_retries=1,
        reasoning_effort=effort,
    )


def planner_effort() -> Literal["low", "medium", "high"]:
    """ORCA_PLANNER_EFFORT (default low): medium and high exceeded the 20 s LLM timeout in live runs."""
    import os

    e = os.environ.get("ORCA_PLANNER_EFFORT", "low")
    return e if e in ("low", "medium", "high") else "low"  # type: ignore[return-value]


def _last_user_text(state: OrcaState) -> str:
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


def _props(config: RunnableConfig) -> dict[str, Any]:
    c = config.get("configurable", {})
    p = c.get("properties") or {}
    return p if isinstance(p, dict) else {}


async def make_graph(
    checkpointer: Checkpointer = None,
    model: BaseChatModel | None = None,
    rewrite_model: BaseChatModel | None = None,
    gateway: Gateway | None = None,
) -> Any:
    """Build the compiled graph. The server passes an AsyncPostgresSaver; tests pass fakes."""
    gw = gateway or MCPGateway()
    planner_model = model or make_model(planner_effort())
    rewriter = rewrite_model or model or make_model("low")
    system = load_prompt("planner")  # first and byte-identical on every call (implicit prompt caching)

    async def prepare(state: OrcaState, config: RunnableConfig) -> dict[str, Any]:
        p = _props(config)
        text = _last_user_text(state)
        lang = language.choose(p.get("lang") or state.get("lang"), state.get("lang"), text)
        return {
            "lang": lang,
            "mode": p.get("mode") or state.get("mode") or "simple",
            "boat_profile": p.get("boat_profile") or state.get("boat_profile") or "small_frp",
            "intent": p.get("intent") or state.get("intent"),
            "digests": [],
            "passages": {},
            "draft": None,
            "rewritten": False,
            "fallback": None,
            "guard": {},
        }

    def route(state: OrcaState) -> str:
        return "button" if state.get("intent") in BUTTONS else "planner"

    async def button(state: OrcaState) -> dict[str, Any]:
        ev = Evidence()
        tools = {t.name: t for t in make_tools(Turn(gw, ev, state.get("boat_profile", "small_frp")))}
        await tools["yukti"].ainvoke({})
        return {"digests": ev.digests, "passages": ev.passages, "draft": None, "fallback": "button"}

    async def planner(state: OrcaState, config: RunnableConfig) -> dict[str, Any]:
        ev = Evidence()
        tools = make_tools(Turn(gw, ev, state.get("boat_profile", "small_frp")))
        agent = create_agent(planner_model, tools, system_prompt=system, response_format=ToolStrategy(Answer))
        history = [
            m
            for m in state["messages"]
            if (isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and not m.tool_calls))
        ]
        context = SystemMessage(
            content=f"Mode: {state.get('mode', 'simple')}. Boat type: "
            f"{state.get('boat_profile', 'small_frp')}. Reply language after translation: "
            f"{state.get('lang', 'en-IN')}."
        )
        try:
            out = await agent.ainvoke(
                {"messages": [context, *history[-12:]]}, {"recursion_limit": 2 * MAX_TOOL_CALLS + 4}
            )
            ans: Answer | None = out.get("structured_response")
        except Exception as e:  # LLM timeout, quota, network: never a made-up answer
            log.warning("planner unavailable: %s: %s", type(e).__name__, str(e)[:500])
            return {"digests": ev.digests, "passages": ev.passages, "draft": None, "fallback": "llm"}
        if ans is None:
            return {"digests": ev.digests, "passages": ev.passages, "draft": None, "fallback": "template"}
        return {"digests": ev.digests, "passages": ev.passages, "draft": ans.model_dump()}

    def _check(state: OrcaState) -> validator.Check:
        d = state.get("draft") or {}
        texts = [validator_text(x) for x in state.get("digests", [])]
        return validator.validate(
            d.get("text", ""),
            d.get("citations", []),
            texts,
            state.get("passages", {}),
            state.get("mode", "simple"),
        )

    async def validate(state: OrcaState) -> dict[str, Any]:
        if state.get("fallback") or not state.get("draft"):
            return {}
        c = _check(state)
        guard = {
            "ungrounded_number": len(c.ungrounded),
            "quote_dropped": len(c.quote_dropped),
            "codes": len(c.codes),
            "unsafe_wording": c.unsafe_wording,
            "rewritten": state.get("rewritten", False),
        }
        if c.ok:
            return {"draft": (state.get("draft") or {}) | {"text": c.text}, "guard": guard}
        if state.get("rewritten"):
            return {"fallback": "template", "guard": guard | {"template_fallback": True}}
        try:
            fixed = await rewriter.with_structured_output(Answer).ainvoke(
                [
                    SystemMessage(content=prompt("rewrite") + "\n- " + "\n- ".join(c.problems())),
                    HumanMessage(
                        content=f"Question: {_last_user_text(state)}\n\nTool outputs:\n"
                        + "\n".join(validator_text(x) for x in state.get("digests", []))
                        + f"\n\nDraft:\n{(state.get('draft') or {}).get('text', '')}"
                    ),
                ]
            )
            draft = fixed.model_dump() if isinstance(fixed, Answer) else None
        except Exception:
            draft = None
        if draft is None:
            return {"fallback": "template", "guard": guard | {"template_fallback": True}}
        return {"draft": draft, "rewritten": True, "guard": guard}

    def after_validate(state: OrcaState) -> str:
        if state.get("fallback") or not state.get("draft"):
            return "finalize"
        if state.get("rewritten") and not state.get("guard", {}).get("rewritten"):
            return "validate"  # check the rewrite
        return "finalize"

    async def finalize(state: OrcaState) -> dict[str, Any]:
        lang = state.get("lang", "en-IN")
        mode = state.get("mode", "simple")
        fallback = state.get("fallback")
        yuktis = [d for d in state.get("digests", []) if d.get("kind") == "yukti" and d.get("verdict")]
        draft = state.get("draft") or {}
        notes: list[str] = []
        translated = False
        if yuktis and (fallback or mode == "simple"):
            body = templates.verdict(yuktis[-1], lang)  # safety wording from approved phrases only
        elif fallback == "llm":
            body = templates.needs_network(lang)
        elif fallback == "template" or not draft.get("text"):
            kb = [d for d in state.get("digests", []) if d.get("kind") == "knowledge"]
            body = templates.nothing_found(lang) if kb and not kb[-1].get("relevant") else templates.cannot_verify(lang)
        else:
            body, note = await language.translate(draft["text"], lang)
            translated = note is None and not lang.startswith("en")
            if note:
                notes.append(note)
        if yuktis and mode == "simple" and draft.get("text") and fallback is None:
            notes.append("Simple mode: the verdict is shown from approved phrases")
        final = f"{body}\n\n{templates.footer(lang)}"
        lang_ok = validator.language_ok(body, lang) if translated or lang.startswith("en") else True
        guard = state.get("guard", {}) | {
            "template_fallback": bool(fallback and fallback != "button"),
            "language_mismatch": not lang_ok,
            "translated": translated,
        }
        record_guardrails(guard)
        answer_id = draft.get("answer_id") or next((y.get("answer_id") for y in reversed(yuktis)), None)
        verified = (
            [c for c in draft.get("citations", []) if c.get("marker", "").strip("[] ") in state.get("passages", {})]
            if fallback is None
            else []
        )
        msg = AIMessage(
            content=final,
            additional_kwargs={
                "answer_id": answer_id,
                "citations": verified,
                "lang": lang,
                "notes": notes,
                "guard": guard,
            },
        )
        return {
            "messages": [msg],
            "answer_id": answer_id,
            "intent": None,
            "evidence": [x for x in [answer_id, *(c["marker"] for c in verified)] if x],
            "digests": [],
            "passages": {},
            "draft": None,
            "rewritten": False,
            "fallback": None,
        }

    g = StateGraph(OrcaState)
    g.add_node("prepare", prepare)
    g.add_node("button", button)
    g.add_node("planner", planner)
    g.add_node("validate", validate)
    g.add_node("finalize", finalize)
    g.add_edge(START, "prepare")
    g.add_conditional_edges("prepare", route, {"button": "button", "planner": "planner"})
    g.add_edge("button", "finalize")
    g.add_edge("planner", "validate")
    g.add_conditional_edges("validate", after_validate, {"validate": "validate", "finalize": "finalize"})
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)


def validator_text(d: dict[str, Any]) -> str:
    from src.digest import dumps

    return dumps(d)
