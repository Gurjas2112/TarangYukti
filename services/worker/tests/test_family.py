"""Family notice (Milestone 8): one notice per grant holder, in their language, then the trip is stamped."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ty_worker import family


class Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class Conn:
    def __init__(self, closed: list[dict[str, Any]], grantees: list[dict[str, Any]]) -> None:
        self.closed, self.grantees = closed, grantees
        self.writes: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, q: str, args: tuple[Any, ...] = ()) -> Result:
        if q is family.CLOSED:
            return Result(self.closed)
        if q is family.GRANTEES:
            return Result(self.grantees)
        self.writes.append((q, args))
        return Result([])


async def test_each_grantee_gets_one_notice_and_the_trip_is_stamped() -> None:
    trip = {
        "id": "t1",
        "boat_id": "b1",
        "name": "Mariamma",
        "home_harbour": "rameswaram",
        "returned_at": datetime(2026, 11, 4, 8, 50, tzinfo=UTC),  # 14:20 IST
    }
    conn = Conn([trip], [{"grantee_id": "u2", "language": "en-IN"}, {"grantee_id": "u3", "language": None}])
    assert await family.notify_family(conn) == 2  # type: ignore[arg-type]
    inserts = [w for w in conn.writes if w[0].lstrip().startswith("insert into alerts")]
    assert len(inserts) == 2
    assert inserts[0][1][3] == "Mariamma is back at Rameswaram, 14:20."
    assert inserts[0][1][5] == "/family/b1"  # app path only, never coordinates
    assert any("family_notified_at" in w[0] for w in conn.writes)


async def test_no_grantees_still_stamps_the_trip() -> None:
    conn = Conn(
        [{"id": "t1", "boat_id": "b1", "name": "B", "home_harbour": None, "returned_at": datetime.now(UTC)}], []
    )
    assert await family.notify_family(conn) == 0  # type: ignore[arg-type]
    assert [w for w in conn.writes if "family_notified_at" in w[0]]
