"""Local scheduler: one APScheduler process runs the same run-once jobs as Container Apps jobs in Tier 1."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import ingest_once, watch_once

log = logging.getLogger("ty_worker")


def build_scheduler() -> AsyncIOScheduler:
    s = AsyncIOScheduler(timezone="UTC")
    s.add_job(watch_once.run, "cron", minute="*/15", id="watch")
    s.add_job(ingest_once.run, "cron", hour=20, minute=30, id="ingest")  # 02:00 IST
    return s


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    build_scheduler().start()
    log.info("ty-worker scheduler started")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(_main())
