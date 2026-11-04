"""Expert console and analyst data (spec §7.5, §11): public, no personal data, cacheable.

- /expert/plan     full Yukti result for a harbour + boat type (+ departure, + fishing spot): verdict, earliest and
                   recommended windows, the Constraint Ledger and the route as GeoJSON
- /layers/{name}   border line (IMBL), marine park, land — GeoJSON, immutable per version
- /grids/{kind}    SST or chlorophyll points (+ /csv download, + /netcdf link to the source)
- /pfz             computed fishing zones (fronts x chlorophyll) and the INCOIS advisory, with the overlap score
- /anomaly         SST anomaly series and the marine-heatwave test at a point
- /sources/chunk/{id}, /kb/documents   citation passages and the knowledge-base list (read as `anon`, RLS)
"""

from __future__ import annotations

import csv
import functools
import hashlib
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import h3
import yaml
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse
from ty_common.db import anon_tx
from ty_common.phrases import harbour as harbour_info
from ty_common.phrases import harbours
from ty_common.settings import find_config_dir

from .public import PUBLIC_CACHE, BoatKind, call_tool

router = APIRouter()
LAYER_FILES = {"imbl": "imbl.geojson", "mpa": "mpa_gom.geojson", "land": "land.geojson"}
Kind = Literal["sst", "chl"]


def layers_dir() -> Path:
    env = os.environ.get("TY_DATA_DIR")
    return Path(env) / "layers" if env else find_config_dir().parent / "data" / "layers"


@functools.cache
def _sources() -> dict[str, Any]:
    doc: dict[str, Any] = yaml.safe_load((find_config_dir() / "sources.yaml").read_text(encoding="utf-8"))
    return doc


@functools.cache
def _region() -> dict[str, float]:
    qc = yaml.safe_load((find_config_dir() / "qc.yaml").read_text(encoding="utf-8"))
    return {k: float(v) for k, v in qc["region"]["bbox"].items()}


@functools.cache
def _config(name: str) -> dict[str, Any]:
    doc: dict[str, Any] = yaml.safe_load((find_config_dir() / name).read_text(encoding="utf-8"))
    return doc


def limits(boat_type: str) -> dict[str, dict[str, Any]]:
    """The limit each ledger row is checked against, from config (constraints.yaml, boats.yaml) — shown next to the
    value in the ledger and used to draw the H2 border buffer."""
    c, b = _config("constraints.yaml"), _config("boats.yaml")[boat_type]
    return {
        "H2": {"value": c["hard"]["H2"]["imbl_min_km"], "unit": "km", "op": ">="},
        "H5": {"value": b["max_wave_m"], "unit": "m", "op": "<="},
        "H6": {"value": b["max_wind_kmh"], "unit": "km/h", "op": "<="},
        "S2": {"value": int(c["soft"]["S2"]["margin"] * 100), "unit": "% fuel margin", "op": ">="},
        "S3": {"value": c["soft"]["S3"]["caution_at"], "unit": "ratio", "op": "<"},
    }


def route_geojson(cells: list[str]) -> dict[str, Any] | None:
    """H3 route cells → LineString through the cell centres (lon, lat)."""
    if len(cells) < 2:
        return None
    coords = [[round(lon, 5), round(lat, 5)] for lat, lon in (h3.cell_to_latlng(c) for c in cells)]
    return {"type": "LineString", "coordinates": coords}


def _parse_depart(depart_at: str | None) -> str | None:
    if depart_at is None:
        return None
    try:
        t = datetime.fromisoformat(depart_at)
    except ValueError as e:
        raise HTTPException(422, "depart_at must be ISO 8601 with a timezone") from e
    if t.tzinfo is None:
        raise HTTPException(422, "depart_at needs a timezone, e.g. +05:30")
    return t.isoformat()


@router.get("/expert/plan")
async def plan(
    response: Response,
    harbour: str,
    boat_type: BoatKind,
    depart_at: str | None = None,
    goal_lat: float | None = None,
    goal_lon: float | None = None,
    lang: str | None = None,
) -> dict[str, Any]:
    if harbour not in harbours():
        raise HTTPException(422, "unknown harbour")
    h = harbour_info(harbour)
    args: dict[str, Any] = {"boat_type": boat_type, "lat": h["lat"], "lon": h["lon"]}
    if (goal_lat is None) != (goal_lon is None):
        raise HTTPException(422, "give both goal_lat and goal_lon")
    if goal_lat is not None:
        args |= {"goal_lat": goal_lat, "goal_lon": goal_lon}
    if (d := _parse_depart(depart_at)) is not None:
        args["depart_at"] = d
    if lang:
        args["lang"] = lang
    r = await call_tool("yukti_evaluate", args)
    if r.get("data", {}).get("available") is False:
        raise HTTPException(502, "the constraint engine could not answer")
    for k in ("requested", "earliest_window", "recommended"):
        ev = r["data"].get(k)
        if ev:
            ev["route"] = route_geojson(ev.get("route_cells") or [])
    r["data"]["harbour"] = {"id": h["id"], "name": h["name"], "lat": h["lat"], "lon": h["lon"]}
    r["data"]["limits"] = limits(boat_type)
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return r


@router.get("/layers/{name}")
async def layer(name: str, response: Response) -> Response:
    if name not in LAYER_FILES:
        raise HTTPException(404, "unknown layer")
    body = (layers_dir() / LAYER_FILES[name]).read_bytes()
    etag = hashlib.sha256(body).hexdigest()[:16]
    return Response(
        body,
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=86400", "ETag": f'"{etag}"'},
    )


@router.get("/grids/{kind}")
async def grid(kind: Kind, response: Response) -> dict[str, Any]:
    r = await call_tool(f"{kind}_grid", {})
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return r


@router.get("/grids/{kind}/csv", response_class=PlainTextResponse)
async def grid_csv(kind: Kind) -> PlainTextResponse:
    r = await call_tool(f"{kind}_grid", {})
    d = r["data"]
    if d.get("available") is False:
        raise HTTPException(503, d.get("reason", "source unavailable"))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["lat", "lon", f"{kind}_{'c' if kind == 'sst' else 'mg_m3'}", "time_utc", "source"])
    for p in d["points"]:
        w.writerow([p["lat"], p["lon"], p["value"], d["time"], r["source"]])
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{kind}_{str(d["time"])[:10]}.csv"',
            "Cache-Control": PUBLIC_CACHE,
        },
    )


@router.get("/grids/{kind}/netcdf")
async def grid_netcdf(kind: Kind) -> dict[str, str]:
    """NetCDF straight from the source (ERDDAP serves the same query as .nc) — no copy kept here."""
    ep = _sources()["endpoints"][kind]
    url = ep["url"].removesuffix(".json") + ".nc"
    return {"url": f"{url}?{ep['query'].format(**_region())}", "source": ep["name"]}


@router.get("/pfz")
async def pfz(response: Response) -> dict[str, Any]:
    computed = await call_tool("pfz_compute", {})
    incois = await call_tool("pfz_incois", {})
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return {"computed": computed, "incois": incois}


@router.get("/anomaly")
async def anomaly(response: Response, lat: float, lon: float, days: int = 30) -> dict[str, Any]:
    r = await call_tool("anomaly_series", {"lat": lat, "lon": lon, "days": days})
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return r


@router.get("/sources/chunk/{chunk_id}")
async def chunk(chunk_id: int, response: Response) -> dict[str, Any]:
    """A citation: the passage, its document, issuer, version and validity (spec §13 provenance API)."""
    async with anon_tx() as cur:
        await cur.execute(
            """select c.id, c.content, c.heading_path, c.topics, c.index_version,
                      d.id as document_id, d.source_id, d.version, d.issuer, d.doc_type, d.language, d.url,
                      d.valid_from, d.valid_to, d.status, d.superseded_by, d.superseded_at
               from kb_chunks c join kb_documents d on d.id = c.document_id where c.id = %s""",
            (chunk_id,),
        )
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(404, "no such passage")
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return {k: (str(v) if k in ("document_id", "superseded_by") and v is not None else v) for k, v in row.items()}


@router.get("/kb/documents")
async def kb_documents(response: Response) -> dict[str, Any]:
    async with anon_tx() as cur:
        await cur.execute(
            """select d.id, d.source_id, d.version, d.issuer, d.doc_type, d.language, d.url, d.status,
                      d.valid_from, d.valid_to, d.ingested_at, d.superseded_at,
                      (select count(*) from kb_chunks c where c.document_id = d.id) as chunks
               from kb_documents d order by d.issuer, d.source_id, d.ingested_at desc"""
        )
        rows = await cur.fetchall()
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return {"documents": [{**r, "id": str(r["id"])} for r in rows]}
