"""imd_warnings, incois_alerts and pfz_incois — official bulletins.

Neither source has a feed this service can call today: the IMD API needs IP whitelisting and INCOIS
publishes HTML/PDF only. So these tools read **normalised snapshot files** (captured by hand or by a
parser, plus clearly labelled simulations from `tarangyukti.sim_warning`). Online mode tries the live
source first and falls back to the snapshot; an old snapshot keeps its old `fetched_at`, so H8 marks
it stale and the verdict can never be GO.

Snapshot file `warnings_imd.json` / `warnings_incois.json` payload:
    {"warnings": [{"id", "issuer", "kind", "title", "districts" | "sectors", "area" (GeoJSON|null),
                   "valid_from", "valid_to", "issued_at", "severity", "simulation", "source_url"}]}
Snapshot file `pfz_incois.json` payload:
    {"issued_at", "valid_to", "sector", "zones": [{"id", "lat", "lon", "text"}], "source_url"}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from ty_common.cache import cached, fingerprint, norm_hour
from ty_common.models import ToolResult

from .. import config, fetch
from ..snapshot import SnapshotStore
from .common import finish, mode_key, now, resolve, unavailable

Issuer = Literal["IMD", "INCOIS"]


class Warning_(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    issuer: Issuer
    kind: str  # high_wave, cyclone, thunderstorm, swell_surge, strong_wind, …
    title: str
    districts: list[str] = []
    sectors: list[str] = []
    area: dict[str, Any] | None = None  # GeoJSON Polygon/MultiPolygon
    valid_from: datetime
    valid_to: datetime
    issued_at: datetime
    severity: Literal["warning", "alert", "watch"]
    simulation: bool = False
    source_url: str


def active(warnings: list[Warning_], at: datetime) -> list[Warning_]:
    return [w for w in warnings if w.valid_from <= at <= w.valid_to]


def _matches(w: Warning_, place: str | None) -> bool:
    if place is None:
        return True
    p = place.strip().casefold()
    return any(p == x.casefold() for x in [*w.districts, *w.sectors])


def _warnings_result(issuer: Issuer, doc: dict[str, Any], place: str | None, at: datetime, store: str) -> ToolResult:
    ws = [Warning_.model_validate(w) for w in doc["payload"]["warnings"]]
    act = [w for w in active(ws, at) if _matches(w, place)]
    notes = [f"snapshot {store}"]
    if any(w.simulation for w in act):
        notes.append("SIMULATION: contains a simulated warning for demonstration")
    ep = config.endpoint("imd" if issuer == "IMD" else "incois_alerts")
    return ToolResult(
        data={
            "issuer": issuer,
            "place": place,
            "at": at.isoformat(),
            "count": len(act),
            "active": [w.model_dump(mode="json") for w in act],
        },
        source=ep["name"],
        source_url=ep["url"],
        fetched_at=datetime.fromisoformat(doc["fetched_at"]),
        valid_at=at,
        confidence="high",
        notes=notes,
    )


def _make_warnings(issuer: Issuer) -> Any:
    snap_name = "warnings_imd" if issuer == "IMD" else "warnings_incois"
    reason = (
        "IMD API requires IP whitelisting (request pending)"
        if issuer == "IMD"
        else "INCOIS publishes alerts as web pages only; no machine-readable feed"
    )

    @cached(
        ns="tool",
        ttl=config.ttl("warnings"),
        key=lambda place, at_hour: fingerprint(snap_name, place, at_hour, *mode_key()),
        tags=lambda place, at_hour: [f"source:{issuer.lower()}"],
    )
    async def run(place: str | None, at_hour: str) -> dict[str, Any]:
        at = now()

        async def online() -> ToolResult:
            # TODO(tarangyukti): live parser once IMD whitelists our IP / INCOIS publishes a feed.
            raise fetch.SourceUnavailable(reason)

        def snap(store: SnapshotStore) -> ToolResult:
            return _warnings_result(issuer, store.read(snap_name), place, at, store.date)

        return await resolve(online, snap)

    return run


_imd, _incois = _make_warnings("IMD"), _make_warnings("INCOIS")


async def imd_warnings(district: str | None = None) -> dict[str, Any]:
    """Active IMD warnings now (port warnings, sea-area bulletins, district thunderstorm nowcasts).

    district: e.g. "Ramanathapuram" (None = all in the region). Each warning has issuer, kind, title,
    validity window (UTC) and a `simulation` flag. No warning listed does NOT mean safe: check `cache`,
    `fetched_at` and `notes` for staleness.
    """
    try:
        return finish(await _imd(district, norm_hour(now())))
    except fetch.SourceUnavailable as e:
        return unavailable("IMD", config.endpoint("imd")["url"], str(e))


async def incois_alerts(sector: str | None = None) -> dict[str, Any]:
    """Active INCOIS ocean-state alerts now (high waves, swell surge, …) for a coastal sector.

    sector: e.g. "Ramanathapuram" or "Gulf of Mannar" (None = all). Same fields as imd_warnings.
    """
    try:
        return finish(await _incois(sector, norm_hour(now())))
    except fetch.SourceUnavailable as e:
        return unavailable("INCOIS", config.endpoint("incois_alerts")["url"], str(e))


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
