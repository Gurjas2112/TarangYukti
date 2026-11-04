"""make push-test USER=<uuid>: queue and send the "Kadal Mitra alerts are on" push to every device of a user."""

from __future__ import annotations

import argparse
import logging

from ty_common.phrases import nearest_language, phrases

from . import outbox
from .runtime import run_async


async def push_test(user_id: str) -> dict[str, int]:
    async with await outbox.connect() as conn:
        pref = await (await conn.execute("select language from user_prefs where user_id = %s", (user_id,))).fetchone()
        p, used = phrases((pref or {}).get("language") or nearest_language(None))
        row = await (
            await conn.execute(
                """insert into alerts (user_id, kind, rule, title, body, lang)
                   values (%s, 'test', 'push-test', 'Kadal Mitra', %s, %s) returning id""",
                (user_id, p["push_test"], used),
            )
        ).fetchone()
        assert row is not None
        return await outbox.send_pending(conn, only=str(row["id"]))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(prog="ty_worker.push_test")
    ap.add_argument("--user", required=True)
    print(run_async(push_test(ap.parse_args().user)))


if __name__ == "__main__":
    main()
