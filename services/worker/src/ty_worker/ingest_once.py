"""ingest_once: implemented in Milestone 2 (snapshots) and 4 (bulletins)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


async def run() -> None:
    # TODO(tarangyukti): implement in Milestone 2 (snapshots) and 4 (bulletins).
    log.info("ingest_once: nothing to do yet")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
