"""Inject one clearly labelled SIMULATED INCOIS high-wave warning into a snapshot (spec Table 16-1).

It covers the Rameswaram area so H1 fires on stage every time. `simulation: true` travels with it, and
every tool result that contains it says SIMULATION in its notes.

    uv run python -m tarangyukti.sim_warning --date 2026-11-02 [--hours 24] [--clear]
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

from .snapshot import SnapshotMissing, SnapshotStore

SIM_ID = "SIM-INCOIS-HW-RAMESWARAM"
# Box around Rameswaram, Pamban and the Palk Bay / Gulf of Mannar waters nearby (on India's side).
AREA = {
    "type": "Polygon",
    "coordinates": [[[79.0, 9.05], [79.45, 9.05], [79.45, 9.45], [79.0, 9.45], [79.0, 9.05]]],
}


def simulated_warning(start: datetime, hours: int) -> dict[str, object]:
    return {
        "id": SIM_ID,
        "issuer": "INCOIS",
        "kind": "high_wave",
        "title": "SIMULATION — High wave alert for the Ramanathapuram coast (demonstration only)",
        "districts": ["Ramanathapuram"],
        "sectors": ["Ramanathapuram", "Gulf of Mannar", "Palk Bay"],
        "area": AREA,
        "valid_from": start.isoformat(),
        "valid_to": (start + timedelta(hours=hours)).isoformat(),
        "issued_at": start.isoformat(),
        "severity": "alert",
        "simulation": True,
        "source_url": "urn:tarangyukti:simulation",
    }


def apply(store: SnapshotStore, hours: int = 24, clear: bool = False) -> int:
    try:
        doc = store.read("warnings_incois")
        warnings = [w for w in doc["payload"]["warnings"] if w["id"] != SIM_ID]
        source_url, fetched_at = doc["source_url"], datetime.fromisoformat(doc["fetched_at"])
    except SnapshotMissing:
        warnings, source_url, fetched_at = (
            [],
            "https://incois.gov.in/site/services/osf.jsp",
            datetime.now(UTC),
        )
    if not clear:
        start = datetime.strptime(store.date, "%Y-%m-%d").replace(tzinfo=UTC)
        warnings.append(simulated_warning(start, hours))
    store.write("warnings_incois", {"warnings": warnings}, source_url, fetched_at)
    store.write_manifest()
    return len(warnings)


def main() -> None:
    ap = argparse.ArgumentParser(prog="tarangyukti.sim_warning")
    ap.add_argument("--date", required=True)
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--clear", action="store_true", help="remove the simulated warning")
    a = ap.parse_args()
    n = apply(SnapshotStore(a.date), a.hours, a.clear)
    print(f"snapshot {a.date}: {n} INCOIS warning(s); simulation {'removed' if a.clear else 'added'}")


if __name__ == "__main__":
    main()
