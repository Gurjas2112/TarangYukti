"""Live IMD and INCOIS warnings from NDMA SACHET, India's official CAP (Common Alerting Protocol) hub.

Free, no registration: the IMD API itself needs IP whitelisting, but IMD regional centres and INCOIS
publish the same alerts as CAP 1.2 through SACHET.

1. `FetchAllAlertDetails` lists every currently active alert (JSON). If it fails, the RSS feed of the
   latest 100 alerts is used instead (it can miss older alerts that are still valid — noted).
2. Alerts whose centre lies near the region are opened: the CAP XML gives the official text, validity
   and the real issuer (state authorities relay INCOIS alerts with `references: INCOIS,…`), and the
   polygon file gives the area. Each CAP file is cached by its identifier (alerts are immutable).
3. An alert counts for the region if its polygon intersects the region box, or — when it has no
   polygon — its area description names a region district or sea.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

import defusedxml.ElementTree as ET
from shapely.geometry import MultiPolygon, Polygon, box, mapping
from ty_common.cache import cached, fingerprint

from .. import config, fetch, qc
from ..snapshot import SnapshotStore
from .alert_model import AnyIssuer, Severity, Warning_

CAP = "{urn:oasis:names:tc:emergency:cap:1.2}"
_SEVERITY: dict[str, Severity] = {"extreme": "warning", "severe": "warning", "moderate": "alert"}
_KINDS = [  # first match wins; checked against the CAP <event>
    ("high wave", "high_wave"),
    ("swell", "high_wave"),
    ("storm surge", "storm_surge"),
    ("tsunami", "tsunami"),
    ("cyclone", "cyclone"),
    ("depression", "cyclone"),
    ("thunder", "thunderstorm"),
    ("lightning", "thunderstorm"),
    ("squall", "strong_wind"),
    ("wind", "strong_wind"),
    ("rain", "heavy_rain"),
]


def sachet() -> dict[str, Any]:
    ep: dict[str, Any] = config.endpoint("sachet")
    return ep


def issuer_of(sender: str, references: str = "") -> AnyIssuer | None:
    """INCOIS if it sent or references INCOIS; IMD if it sent or references IMD; SDMA for a state
    disaster authority's own alert; None otherwise."""
    snd, ref = sender.strip().upper(), references.strip().upper()
    if snd.startswith("INCOIS") or ref.startswith("INCOIS"):
        return "INCOIS"
    if snd.startswith("IMD") or ref.startswith("IMD"):
        return "IMD"
    if "SDMA" in snd:
        return "SDMA"
    return None


def kind_of(event: str) -> str:
    e = event.casefold()
    return next((k for needle, k in _KINDS if needle in e), re.sub(r"[^a-z0-9]+", "_", e).strip("_") or "other")


# ── listing ──────────────────────────────────────────────────────────────────────


async def list_active() -> tuple[list[dict[str, str]], list[str]]:
    """[{identifier, source}] of active alerts from the wanted offices, plus notes."""
    ep = sachet()
    try:
        rows = await fetch.get_json(ep["active_url"], timeout=60)
        items = [
            {
                "identifier": str(r["identifier"]),
                "source": str(r.get("alert_source", "")),
                "centroid": r.get("centroid"),
            }
            for r in rows
        ]
        notes: list[str] = []
    except fetch.SourceUnavailable as e:
        items = await _list_rss()
        notes = [f"active-alert list unavailable ({e}); used the latest-100 RSS feed, which can miss older alerts"]
    wanted = []
    for it in items:
        c = it.get("centroid")
        near = _centroid_near(c) if c else it["source"] in set(ep["rss_sources"])
        if near:
            wanted.append({"identifier": it["identifier"], "source": it["source"]})
    return wanted, notes


def _centroid_near(centroid: str) -> bool:
    """Cheap pre-filter on SACHET's 'lon,lat' centroid: within the region box grown by the configured margin."""
    try:
        lon, lat = (float(x) for x in centroid.split(","))
    except ValueError:
        return True
    b, m = qc.bbox(), float(sachet()["prefilter_margin_deg"])
    return b["lat_min"] - m <= lat <= b["lat_max"] + m and b["lon_min"] - m <= lon <= b["lon_max"] + m


async def _list_rss() -> list[dict[str, str]]:
    raw = await fetch.get_bytes(sachet()["rss_url"], timeout=60)
    out = []
    for item in ET.fromstring(raw).iter("item"):
        author = item.findtext("author") or ""
        m = re.search(r"\(([^)]+)\)", author)
        out.append({"identifier": (item.findtext("guid") or "").strip(), "source": m.group(1) if m else author})
    return out


# ── one CAP alert ────────────────────────────────────────────────────────────────


def parse_polygons(raw: bytes) -> MultiPolygon | None:
    polys = []
    for el in ET.fromstring(raw).iter("polygon"):
        pts = []
        for pair in (el.text or "").split():
            lat_s, _, lon_s = pair.partition(",")
            try:
                pts.append((float(lon_s), float(lat_s)))
            except ValueError:
                continue
        if len(pts) >= 4:
            p = Polygon(pts)
            polys.append(p if p.is_valid else p.buffer(0))
    if not polys:
        return None
    parts: list[Polygon] = []
    for p in polys:
        parts.extend(p.geoms if isinstance(p, MultiPolygon) else [p])
    return MultiPolygon(parts)


def _info(root: Any) -> Any:
    infos = root.findall(f"{CAP}info")
    return next((i for i in infos if (i.findtext(f"{CAP}language") or "").lower().startswith("en")), infos[0])


def _names(area_desc: str) -> list[str]:
    """'Ranipet, Tirupathur districts of Tamil Nadu' → ['Ranipet', 'Tirupathur']."""
    head = re.split(r"\b(?:districts?|zones?|coasts?)\s+of\b", area_desc, flags=re.I)[0]
    return [n.strip(" .") for n in re.split(r",|\band\b", head) if n.strip(" .")]


def parse_cap(raw: bytes, office: str, url: str, area: MultiPolygon | None) -> Warning_ | None:
    root = ET.fromstring(raw)
    issuer = issuer_of(root.findtext(f"{CAP}sender") or office, root.findtext(f"{CAP}references") or "")
    if issuer is None or (root.findtext(f"{CAP}status") or "").strip() != "Actual":
        return None
    info = _info(root)
    event = (info.findtext(f"{CAP}event") or "").strip()
    cap_sev = (info.findtext(f"{CAP}severity") or "Unknown").strip()
    area_desc = " ".join(a.findtext(f"{CAP}areaDesc") or "" for a in info.findall(f"{CAP}area")).strip()
    names = _names(area_desc)
    start = info.findtext(f"{CAP}effective") or info.findtext(f"{CAP}onset") or root.findtext(f"{CAP}sent")
    return Warning_(
        id=(root.findtext(f"{CAP}identifier") or "").strip(),
        issuer=issuer,
        kind=kind_of(event),
        title=(info.findtext(f"{CAP}headline") or event).strip(),
        event=event or None,
        cap_severity=cap_sev,
        office=office,
        area_desc=area_desc or None,
        districts=names if issuer != "INCOIS" else [],
        sectors=names if issuer == "INCOIS" else [],
        area=mapping(area.simplify(0.005, preserve_topology=True)) if area is not None else None,
        valid_from=datetime.fromisoformat(str(start).strip()),
        valid_to=datetime.fromisoformat((info.findtext(f"{CAP}expires") or "").strip()),
        issued_at=datetime.fromisoformat((root.findtext(f"{CAP}sent") or "").strip()),
        severity=_SEVERITY.get(cap_sev.casefold(), "watch"),
        source_url=url,
    )


def in_region(w: Warning_) -> bool:
    b = qc.bbox()
    region = box(b["lon_min"], b["lat_min"], b["lon_max"], b["lat_max"])
    if w.area is not None:
        from shapely.geometry import shape

        return bool(shape(w.area).intersects(region))
    text = (w.area_desc or "").casefold()
    return any(n.casefold() in text for n in config.qc()["region"]["alert_area_names"])


@cached(
    ns="tool",
    ttl=86400,
    key=lambda identifier, office: fingerprint("cap_alert", identifier, office),
    tags=lambda identifier, office: ["source:sachet"],
)
async def cap_alert(identifier: str, office: str) -> dict[str, Any] | None:
    """One CAP alert, normalised (immutable per identifier). None if not an actual official alert."""
    ep = sachet()
    url = ep["cap_url"].format(identifier=identifier)
    raw = await fetch.get_bytes(url, timeout=60)
    area = None
    try:
        area = parse_polygons(await fetch.get_bytes(ep["polygon_url"].format(identifier=identifier), timeout=90))
    except (fetch.SourceUnavailable, ET.ParseError):
        area = None  # falls back to the area description
    w = parse_cap(raw, office, url, area)
    return None if w is None else w.model_dump(mode="json")


async def regional_warnings(issuer: AnyIssuer) -> tuple[list[Warning_], list[str]]:
    """Active alerts from `issuer` that touch the region, with notes. State-authority alerts in the region
    that cite neither IMD nor INCOIS are named in the notes (H1 decides what to do with them)."""
    items, notes = await list_active()
    sem = asyncio.Semaphore(4)

    async def one(it: dict[str, str]) -> Warning_ | None:
        async with sem:
            try:
                d = await cap_alert(it["identifier"], it["source"])
            except (fetch.SourceUnavailable, ET.ParseError, ValueError) as e:
                notes.append(f"alert {it['identifier']} unreadable: {e}")
                return None
        return Warning_.model_validate(d) if d else None

    ws = [w for w in await asyncio.gather(*(one(i) for i in items)) if w is not None and in_region(w)]
    for w in ws:
        if w.issuer == "SDMA" and issuer != "SDMA":
            notes.append(
                f"state authority alert in region, not attributed to IMD/INCOIS: {w.office}: {w.event} "
                f"until {w.valid_to.isoformat()} ({w.id})"
            )
    return [w for w in ws if w.issuer == issuer], notes


async def capture(store: SnapshotStore, issuer: AnyIssuer) -> None:
    """Snapshot the region's active alerts; simulated warnings already in the file are kept."""
    name = {"IMD": "warnings_imd", "INCOIS": "warnings_incois", "SDMA": "warnings_sdma"}[issuer]
    kept: list[dict[str, Any]] = []
    if store.has(name):
        kept = [w for w in store.read(name)["payload"]["warnings"] if w.get("simulation")]
    ws, notes = await regional_warnings(issuer)
    payload = {"warnings": [w.model_dump(mode="json") for w in ws] + kept, "notes": notes}
    store.write(name, payload, sachet()["active_url"])
