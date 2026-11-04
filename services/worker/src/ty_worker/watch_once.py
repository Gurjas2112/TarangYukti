"""watch_once (every 15 minutes): morning briefs and the border safety-net sweep over live positions."""

from __future__ import annotations

import logging

from . import family, morning, outbox
from .runtime import run_async

log = logging.getLogger(__name__)


async def run() -> None:
    n = await morning.run()
    async with await outbox.connect() as conn:
        border = await family.sweep_border(conn)
        if border:
            await outbox.send_pending(conn)
    log.info("watch_once: %d briefs, %d border alerts queued", n, border)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_async(run())
