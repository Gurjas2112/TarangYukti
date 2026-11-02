"""Shared plumbing for data tools: online vs snapshot, fallback, cache flag and the "unavailable" result.

Resolution order (prompt §2 rule 9, spec §13.3 step 6.4):
- DATA_MODE=snapshot → only the dated snapshot (cache="snapshot").
- DATA_MODE=online   → the live source; if it is down, the configured snapshot with a note
                       (its old `fetched_at` lets H8 mark the input stale); else "unavailable".
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from ty_common.cache import config_version, last_outcome
from ty_common.models import ToolResult
from ty_common.settings import get_settings

from ..fetch import SourceUnavailable
from ..snapshot import SnapshotMissing, SnapshotStore, active_store

log = logging.getLogger(__name__)


_frozen: datetime | None = None


def now() -> datetime:
    """Current UTC time, or the frozen time set by tests with freeze()."""
    return _frozen or datetime.now(UTC)


def freeze(at: datetime | None) -> None:
    global _frozen
    _frozen = at


def mode_key() -> tuple[str, str, str]:
    """Part of every tool cache key: data mode, snapshot date and config version."""
    s = get_settings()
    return (s.data_mode, s.snapshot_date or "", config_version())


async def snapshot_store() -> SnapshotStore:
    store = active_store()
    if store is not None:
        return store
    date = get_settings().snapshot_date
    if not date:
        raise SnapshotMissing("SNAPSHOT_DATE is not set")
    store = SnapshotStore(date)
    try:  # not on disk yet: fetch it once from Supabase Storage
        await store.download()
    except Exception as e:
        raise SnapshotMissing(f"snapshot {date} not available locally or in Storage: {e}") from e
    return store


async def resolve(
    online: Callable[[], Awaitable[ToolResult]],
    from_snapshot: Callable[[SnapshotStore], ToolResult],
) -> dict[str, Any]:
    """Run the right path and return the ToolResult as JSON. Raises SourceUnavailable if nothing answers."""
    if get_settings().data_mode == "snapshot":
        try:
            r = from_snapshot(await snapshot_store())
        except SnapshotMissing as e:
            raise SourceUnavailable(str(e)) from e
        return r.model_copy(update={"cache": "snapshot"}).model_dump(mode="json")
    try:
        return (await online()).model_dump(mode="json")
    except SourceUnavailable as live_error:
        try:
            r = from_snapshot(await snapshot_store())
        except SnapshotMissing:
            raise live_error from None
        log.info("live source down, serving snapshot: %s", live_error)
        notes = [
            *r.notes,
            f"live source unavailable ({live_error}); using snapshot {get_settings().snapshot_date}",
        ]
        return r.model_copy(update={"cache": "snapshot", "confidence": "low", "notes": notes}).model_dump(mode="json")


def finish(result: dict[str, Any]) -> dict[str, Any]:
    """Stamp hit/miss from the cache unless the result is already snapshot or stale."""
    if result.get("cache") not in ("snapshot", "stale"):
        outcome = last_outcome()
        result = result | {"cache": "hit" if outcome == "hit" else "miss"}
    return result


def unavailable(source: str, source_url: str, reason: str) -> dict[str, Any]:
    """Nothing could answer. Data says so explicitly; H8 turns it into "unknown" — never GO."""
    return ToolResult(
        data={"available": False, "reason": reason},
        source=source,
        source_url=source_url,
        fetched_at=now(),
        confidence="low",
        cache="miss",
        notes=[reason],
    ).model_dump(mode="json")
