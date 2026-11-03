"""kb_index job: index allow-listed documents and the region's live bulletins into kb_documents / kb_chunks.

uv run python -m ty_worker.kb_index [--only SOURCE_ID ...] [--no-bulletins]
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from .kb import ingest

log = logging.getLogger(__name__)


async def run() -> None:
    """Scheduled entry point (nightly with ingest_once)."""
    report = await ingest.run()
    log.info("kb_index: %s", ingest.summary(report))


def main() -> None:
    ap = argparse.ArgumentParser(prog="ty_worker.kb_index")
    ap.add_argument("--only", nargs="*", help="source_ids to index (default: all)")
    ap.add_argument("--no-bulletins", action="store_true", help="skip live CAP bulletins")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    report = asyncio.run(ingest.run(set(a.only) if a.only else None, with_bulletins=not a.no_bulletins))
    print(ingest.summary(report))
    raise SystemExit(1 if report.failed else 0)


if __name__ == "__main__":
    main()
