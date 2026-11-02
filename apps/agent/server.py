"""ty-agent service (:8123).

Milestone 1: health route only. Milestone 5 adds POST /agent (LangGraphAGUIAgent streamed through
ag_ui.encoder.EventEncoder), AsyncPostgresSaver in schema `agent`, owner-bound threads and the purge —
copied from spec §6.4.5. Never run `langgraph dev` in Tier 1.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="ty-agent", version="0.1.0")


@app.get("/ok")
async def ok() -> dict[str, bool]:
    return {"ok": True}
