"""ty-agent service (spec §6.4.5): FastAPI + AG-UI, thread memory in Postgres (schema `agent`).

    uv run uvicorn server:app --port 8123          (never `langgraph dev` outside your own debugging)

- POST /agent  streams one run over AG-UI. The Supabase token (forwarded by ty-copilot) identifies the user;
               no token = anonymous public thread. The first caller owns a thread; another user gets 403.
               One run per thread at a time (Redis lock, 120 s): a second concurrent request gets 409.
- GET /ok      health.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

if sys.platform == "win32":  # psycopg async needs a selector event loop on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder
from copilotkit import LangGraphAGUIAgent
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from ty_common.auth import current_user
from ty_common.cache import get_cache
from ty_common.settings import get_settings
from ty_common.telemetry import init_tracing, trace_context

from main import make_graph, prompt_version

state: dict[str, Any] = {}
LOCK_S = 120


async def open_memory() -> tuple[Any, Any]:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    s = get_settings()
    if s.agent_database_url is None:
        raise RuntimeError("AGENT_DATABASE_URL is not set (run: uv run python -m ty_worker.db_roles)")
    pool = AsyncConnectionPool(
        s.agent_database_url.get_secret_value(),
        min_size=1,
        max_size=10,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": "-c search_path=agent",
        },
    )
    await pool.open()
    saver = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
    await saver.setup()  # idempotent: checkpoint tables in schema agent
    async with pool.connection() as c:  # ty_agent owns these tables: let the worker purge them (spec §6.4.5)
        await c.execute("grant select, delete on all tables in schema agent to ty_worker")
        await c.execute("alter default privileges in schema agent grant select, delete on tables to ty_worker")
    return pool, saver


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_tracing("ty-agent")
    pool, saver = await open_memory()
    state.update(pool=pool, graph=await make_graph(saver))
    yield
    await pool.close()


app = FastAPI(title="ty-agent", version="0.2.0", lifespan=lifespan)


@app.get("/ok")
async def ok() -> dict[str, bool]:
    return {"ok": True}


async def claim_thread(thread_id: str, user_id: str | None) -> None:
    """Bind a thread to its first caller; refuse anyone else."""
    async with state["pool"].connection() as c:
        row = await (
            await c.execute(
                """insert into agent.threads (thread_id, user_id) values (%s, %s)
               on conflict (thread_id) do update set last_seen = now()
               returning user_id""",
                (thread_id, user_id),
            )
        ).fetchone()
    owner = row["user_id"]
    if owner is not None and str(owner) != user_id:
        raise HTTPException(403, "thread belongs to another user")


async def acquire(thread_id: str) -> bool:
    """Redis lock thread:<id>. If Redis is down the run goes ahead (single-replica laptop)."""
    cache = get_cache()
    if not await cache.redis_available():
        return True
    try:
        return bool(await cache.redis.set(f"thread:{thread_id}", 1, nx=True, ex=LOCK_S))
    except Exception:
        return True


async def release(thread_id: str) -> None:
    cache = get_cache()
    try:
        if await cache.redis_available():
            await cache.redis.delete(f"thread:{thread_id}")
    except Exception:
        pass


@app.post("/agent")
async def run(body: RunAgentInput, request: Request, user: dict[str, Any] | None = Depends(current_user)) -> Any:
    uid = user["sub"] if user else None
    await claim_thread(body.thread_id, uid)
    if not await acquire(body.thread_id):
        raise HTTPException(409, "another answer for this conversation is still running")
    props = body.forwarded_props if isinstance(body.forwarded_props, dict) else {}
    agent = LangGraphAGUIAgent(
        name="orca",
        description="TarangYukti marine copilot",
        graph=state["graph"],
        config={"configurable": {"auth_user": user, "properties": props}},
    )
    encoder = EventEncoder(accept=request.headers.get("accept") or "text/event-stream")
    versions = {"model": get_settings().orca_model, "prompt_version": prompt_version()}

    async def events() -> AsyncIterator[str]:
        try:
            with trace_context(
                thread_id=body.thread_id,
                user_sub=uid,
                lang=str(props.get("lang", "")),
                mode=str(props.get("mode", "simple")),
                versions=versions,
            ):
                async for event in agent.run(body):  # type: ignore[no-untyped-call]
                    yield encoder.encode(event)
        finally:
            await release(body.thread_id)

    return StreamingResponse(events(), media_type=encoder.get_content_type())
