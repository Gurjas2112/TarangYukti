"""Answer records and kill switches (spec §9.5).

- Every reply is stored in public.answers with the model, prompt version and config version that produced it,
  its guard flags and the Yukti ledger id — so any answer can be traced and replayed (admin Replay, Guardrail
  review). The question and reply are kept 180 days (retention job), visible only to their owner and to staff.
- The admin console's "free-form chat off" switch is read here (cached 30 s): button flows keep answering from the
  ledger; free-form questions get the approved "paused" phrase.
Recording is best effort: a database hiccup never blocks a safety answer.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Protocol

log = logging.getLogger(__name__)
FLAG_TTL_S = 30.0


class Recorder(Protocol):
    async def record(self, row: dict[str, Any]) -> None: ...

    async def free_chat_off(self) -> bool: ...


class NullRecorder:
    """Tests and local runs without a database."""

    def __init__(self, chat_off: bool = False) -> None:
        self.rows: list[dict[str, Any]] = []
        self.chat_off = chat_off

    async def record(self, row: dict[str, Any]) -> None:
        self.rows.append(row)

    async def free_chat_off(self) -> bool:
        return self.chat_off


INSERT = """
insert into public.answers (thread_id, user_id, lang, mode, question, reply, verdict, ledger_answer_id, citations,
                            guard, fallback, model, prompt_version, config_version)
values (%(thread_id)s, %(user_id)s, %(lang)s, %(mode)s, %(question)s, %(reply)s, %(verdict)s, %(ledger_answer_id)s,
        %(citations)s::jsonb, %(guard)s::jsonb, %(fallback)s, %(model)s, %(prompt_version)s, %(config_version)s)
"""


class PostgresRecorder:
    def __init__(self, pool: Any) -> None:
        self.pool = pool
        self._flag: tuple[float, bool] = (0.0, False)

    async def record(self, row: dict[str, Any]) -> None:
        params = {**row, "citations": json.dumps(row["citations"]), "guard": json.dumps(row["guard"])}
        try:
            async with self.pool.connection() as c:
                await c.execute(INSERT, params)
        except Exception as e:
            log.warning("answer record failed: %s", type(e).__name__)

    async def free_chat_off(self) -> bool:
        at, value = self._flag
        if time.monotonic() - at < FLAG_TTL_S:
            return value
        try:
            async with self.pool.connection() as c:
                row = await (await c.execute("select value from public.flags where key = 'free_chat_off'")).fetchone()
            value = bool(row and row["value"] is True)
        except Exception as e:  # unknown switch state: keep the last known value
            log.warning("flag read failed: %s", type(e).__name__)
        self._flag = (time.monotonic(), value)
        return value
