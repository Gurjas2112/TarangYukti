"""watch_once (every 15 minutes): morning briefs and the border safety-net sweep over live positions."""

from __future__ import annotations

import logging

from . import family, housekeeping, morning, outbox
from .runtime import run_async

log = logging.getLogger(__name__)


async def run() -> None:
    n = await morning.run()
    async with await outbox.connect() as conn:
        try:
            areas = await housekeeping.refresh_warning_areas(conn)  # officer view + admin live map
        except Exception as e:
            log.warning("warning areas not refreshed: %s", type(e).__name__)
            areas = 0
        border = await family.sweep_border(conn)
        if border:
            await outbox.send_pending(conn)
    log.info("watch_once: %d briefs, %d border alerts, %d warning areas", n, border, areas)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_async(run())
