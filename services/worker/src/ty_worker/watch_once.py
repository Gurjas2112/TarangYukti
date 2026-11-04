"""watch_once (every 15 minutes): morning briefs now; trips and border/warning alerts arrive in Milestone 8."""

from __future__ import annotations

import logging

from . import morning
from .runtime import run_async

log = logging.getLogger(__name__)


async def run() -> None:
    n = await morning.run()
    log.info("watch_once: %d briefs queued", n)
    # TODO(tarangyukti): Milestone 8 adds the fence sweep over live positions and trip open/close.


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_async(run())
