"""Boundary layers (data/layers/*.geojson, built by layers_build.py) in a metric projection.

Distances use UTM zone 44N (EPSG:32644), which covers the region; error is far below the 0.1 km reported.
"""

from __future__ import annotations

import functools
import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import shapely
from pyproj import Transformer
from shapely import Geometry
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.prepared import PreparedGeometry, prep

from . import config

_TO_M = Transformer.from_crs(4326, 32644, always_xy=True).transform


def transform(_fn: object, geom: Geometry) -> Geometry:
    """lon/lat → UTM 44N metres for any geometry."""
    return shapely.transform(geom, lambda xy: np.column_stack(_TO_M(xy[:, 0], xy[:, 1])))


@dataclass(frozen=True)
class Layers:
    imbl: LineString  # metres
    india_side: PreparedGeometry  # metres
    mpa: Geometry  # metres
    mpa_prepared: PreparedGeometry
    land_prepared: PreparedGeometry  # metres
    imbl_props: dict[str, Any]
    mpa_props: dict[str, Any]
    land_props: dict[str, Any]
    version: str  # SHA-256 of the layer files (cache key for the `layer` namespace)


def _read(name: str) -> tuple[dict[str, Any], bytes]:
    raw = (config.data_dir() / "layers" / f"{name}.geojson").read_bytes()
    feat = json.loads(raw)["features"][0]
    return feat, raw


@functools.cache
def load() -> Layers:
    imbl_f, imbl_raw = _read("imbl")
    mpa_f, mpa_raw = _read("mpa_gom")
    land_f, land_raw = _read("land")
    line_ll = shape(imbl_f["geometry"])
    coords = list(line_ll.coords)
    # India is on the north-west (left) side of the SW → NE line: close the polygon around that side.
    (x0, y0), (x1, _) = coords[0], coords[-1]
    india_ll = Polygon([*coords, (x1, 30.0), (60.0, 30.0), (60.0, y0), (x0, y0)])
    return Layers(
        imbl=transform(_TO_M, line_ll),
        india_side=prep(transform(_TO_M, india_ll)),
        mpa=(mpa_m := transform(_TO_M, shape(mpa_f["geometry"]))),
        mpa_prepared=prep(mpa_m),
        land_prepared=prep(transform(_TO_M, shape(land_f["geometry"]))),
        imbl_props=imbl_f["properties"],
        mpa_props=mpa_f["properties"],
        land_props=land_f["properties"],
        version=hashlib.sha256(imbl_raw + mpa_raw + land_raw).hexdigest(),
    )


def point_m(lat: float, lon: float) -> Point:
    x, y = _TO_M(lon, lat)
    return Point(x, y)


def to_m(geom: Geometry) -> Geometry:
    return transform(_TO_M, geom)


@dataclass(frozen=True)
class FenceFlags:
    cell: str
    imbl_min_km: float  # from any part of the cell to the IMBL
    beyond_or_crossing: bool  # centre on the far side, or the cell touches the line
    touches_mpa: bool
    land: bool  # cell centre on land (Natural Earth 1:10m)


@functools.lru_cache(maxsize=50_000)
def fence_flags(cell: str) -> FenceFlags:
    """Per-H3-cell fence flags, computed once per process (route search calls this thousands of times)."""
    import h3

    ly = load()
    poly = to_m(Polygon([(lon, lat) for lat, lon in h3.cell_to_boundary(cell)]))
    lat, lon = h3.cell_to_latlng(cell)
    centre = point_m(lat, lon)
    min_km = round(ly.imbl.distance(poly) / 1000.0, 2)
    return FenceFlags(
        cell=cell,
        imbl_min_km=min_km,
        beyond_or_crossing=(not ly.india_side.contains(centre)) or min_km == 0.0,
        touches_mpa=bool(ly.mpa_prepared.intersects(poly)),
        land=bool(ly.land_prepared.contains(centre)),
    )
