"""imd_warnings, incois_alerts and pfz_incois — official bulletins.

Warnings: live from NDMA SACHET, the official CAP hub where IMD regional centres and INCOIS publish
their alerts (see cap.py; free, no IP whitelisting). If SACHET is down, the configured snapshot is
used; an old snapshot keeps its old `fetched_at`, so H8 marks it stale and the verdict is never GO.
`DATA_MODE=snapshot` reads only the snapshot (which may also hold a labelled SIMULATION).

PFZ: INCOIS publishes advisories as web pages only, so PFZ comes from snapshots.

Snapshot file `warnings_imd.json` / `warnings_incois.json` payload: {"warnings": [Warning_, …]}
Snapshot file `pfz_incois.json` payload:
    {"issued_at", "valid_to", "sector", "zones": [{"id", "lat", "lon", "text"}], "source_url"}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ty_common.cache import cached, fingerprint, norm_hour
from ty_common.models import ToolResult

from .. import config, fetch
from ..snapshot import SnapshotStore
from . import cap
from .alert_model import AnyIssuer, Warning_, active
from .common import finish, mode_key, now, resolve, unavailable

SNAP_NAME: dict[AnyIssuer, str] = {"IMD": "warnings_imd", "INCOIS": "warnings_incois", "SDMA": "warnings_sdma"}
ENDPOINT: dict[AnyIssuer, str] = {"IMD": "imd", "INCOIS": "incois_alerts", "SDMA": "sdma_alerts"}


def _matches(w: Warning_, place: str | None) -> bool:
    if place is None:
        return True
    p = place.strip().casefold()
    return any(p == x.casefold() for x in [*w.districts, *w.sectors]) or p in (w.area_desc or "").casefold()


def _result(
    issuer: AnyIssuer,
    warnings: list[Warning_],
    place: str | None,
    at: datetime,
    fetched_at: datetime,
    notes: list[str],
) -> ToolResult:
    act = [w for w in active(warnings, at) if _matches(w, place)]
    upcoming = sorted((w for w in warnings if w.valid_from > at and _matches(w, place)), key=lambda w: w.valid_from)
    if any(w.simulation for w in [*act, *upcoming]):
        notes = [*notes, "SIMULATION: contains a simulated warning for demonstration"]
    ep = config.endpoint(ENDPOINT[issuer])
    return ToolResult(
        data={
            "issuer": issuer,
            "place": place,
            "at": at.isoformat(),
            "count": len(act),
            "active": [w.model_dump(mode="json") for w in act],
            "upcoming": [w.model_dump(mode="json") for w in upcoming],
        },
        source=ep["name"],
        source_url=ep["url"],
        fetched_at=fetched_at,
        valid_at=at,
        confidence="high",
        notes=notes,
    )


def _make_warnings(issuer: AnyIssuer) -> Any:
    snap_name = SNAP_NAME[issuer]

    @cached(
        ns="tool",
        ttl=config.ttl("warnings"),
        key=lambda place, at_hour: fingerprint(snap_name, place, at_hour, *mode_key()),
        tags=lambda place, at_hour: [f"source:{issuer.lower()}"],
    )
    async def run(place: str | None, at_hour: str) -> dict[str, Any]:
        at = now()

        async def online() -> ToolResult:
            fetched = now()
            ws, notes = await cap.regional_warnings(issuer)
            return _result(issuer, ws, place, at, fetched, ["live CAP alerts from NDMA SACHET", *notes])

        def snap(store: SnapshotStore) -> ToolResult:
            doc = store.read(snap_name)
            ws = [Warning_.model_validate(w) for w in doc["payload"]["warnings"]]
            return _result(issuer, ws, place, at, datetime.fromisoformat(doc["fetched_at"]), [f"snapshot {store.date}"])

        return await resolve(online, snap)

    return run


_imd, _incois, _sdma = _make_warnings("IMD"), _make_warnings("INCOIS"), _make_warnings("SDMA")


async def imd_warnings(district: str | None = None) -> dict[str, Any]:
    """Active IMD warnings now for the Gulf of Mannar / Palk Bay region (IMD Chennai CAP alerts:
    district nowcasts such as thunderstorm and lightning, heavy rain, strong wind, cyclone).

    district: e.g. "Ramanathapuram" (None = every alert touching the region). Each warning has issuer,
    kind, event, CAP severity, title, area, validity window and a `simulation` flag. No warning listed
    does NOT mean safe: check `cache`, `fetched_at` and `notes` for staleness.
    """
    try:
        return finish(await _imd(district, norm_hour(now())))
    except fetch.SourceUnavailable as e:
        return unavailable(config.endpoint("imd")["name"], config.endpoint("imd")["url"], str(e))


async def incois_alerts(sector: str | None = None) -> dict[str, Any]:
    """Active INCOIS ocean-state alerts now for the region (high waves, swell surge, storm surge,
    tsunami), from INCOIS CAP alerts.

    sector: e.g. "Ramanathapuram" or "Gulf of Mannar" (None = every alert touching the region).
    Same fields as imd_warnings.
    """
    try:
        return finish(await _incois(sector, norm_hour(now())))
    except fetch.SourceUnavailable as e:
        return unavailable(config.endpoint("incois_alerts")["name"], config.endpoint("incois_alerts")["url"], str(e))


async def sdma_alerts(district: str | None = None) -> dict[str, Any]:
    """Active alerts the state disaster authority issued on its own (not citing IMD or INCOIS) for the
    region, e.g. lightning or cyclone advisories from Tamil Nadu SDMA. Rule H1 counts them too.
    Same fields as imd_warnings."""
    try:
        return finish(await _sdma(district, norm_hour(now())))
    except fetch.SourceUnavailable as e:
        return unavailable(config.endpoint("sdma_alerts")["name"], config.endpoint("sdma_alerts")["url"], str(e))


# ── PFZ ─────────────────────────────────────────────────────────────────────────


@cached(
    ns="tool",
    ttl=config.ttl("pfz"),
    key=lambda sector, day: fingerprint("pfz_incois", sector, day, *mode_key()),
    tags=lambda sector, day: ["source:incois-pfz"],
)
async def _pfz(sector: str | None, day: str) -> dict[str, Any]:
    async def online() -> ToolResult:
        raise fetch.SourceUnavailable("INCOIS PFZ advisories are published as web pages only; no feed")

    def snap(store: SnapshotStore) -> ToolResult:
        doc = store.read("pfz_incois")
        p = doc["payload"]
        if sector and p.get("sector", "").casefold() != sector.strip().casefold():
            raise fetch.SourceUnavailable(f"snapshot PFZ covers sector {p.get('sector')!r}, not {sector!r}")
        valid_to = datetime.fromisoformat(p["valid_to"])
        notes = [f"snapshot {store.date}"]
        if valid_to < now():
            notes.append("advisory has expired")
        ep = config.endpoint("incois_pfz")
        return ToolResult(
            data={
                "sector": p.get("sector"),
                "issued_at": p["issued_at"],
                "valid_to": p["valid_to"],
                "zones": p["zones"],
            },
            source=ep["name"],
            source_url=p.get("source_url", ep["url"]),
            fetched_at=datetime.fromisoformat(doc["fetched_at"]),
            valid_at=datetime.fromisoformat(p["issued_at"]),
            confidence="high" if valid_to >= now() else "low",
            notes=notes,
        )

    return await resolve(online, snap)


async def pfz_incois(sector: str | None = None) -> dict[str, Any]:
    """The latest official INCOIS Potential Fishing Zone advisory: zone points (lat, lon) with their text.

    sector: e.g. "Tamil Nadu" (None = whatever the snapshot holds). Expired advisories are flagged.
    """
    try:
        return finish(await _pfz(sector, norm_hour(now())[:10]))
    except fetch.SourceUnavailable as e:
        return unavailable("INCOIS PFZ advisory", config.endpoint("incois_pfz")["url"], str(e))
