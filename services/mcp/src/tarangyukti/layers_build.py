"""Build the boundary layers in data/layers/ from their official sources (run once; output is committed).

    uv run python -m tarangyukti.layers_build

- IMBL: positions copied from the two India–Sri Lanka agreements (UN DOALOS treaty texts).
  The treaties define great-circle arcs; over these segment lengths a straight line in lat/lon differs by
  far less than the 0.1 km we report.
- Gulf of Mannar: WDPA polygon 556326231 "Gulf of Mannar National Park" (Eco-Sensitive Zone, 2020). It is
  a ring around the park, so its holes (the park islands and their waters) are filled: the layer is the
  park plus its eco-sensitive zone, which errs on the safe side for H3.
"""

from __future__ import annotations

import json

import httpx
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union
from ty_common.settings import find_config_dir

TREATY_1974 = "https://www.un.org/depts/los/LEGISLATIONANDTREATIES/PDFFILES/TREATIES/LKA-IND1974BW.PDF"
TREATY_1976 = "https://www.un.org/depts/los/LEGISLATIONANDTREATIES/PDFFILES/TREATIES/LKA-IND1976MB.PDF"
WDPA_QUERY = (
    "https://data-gis.unep-wcmc.org/server/rest/services/ProtectedSites/"
    "The_World_Database_of_Protected_Areas/MapServer/1/query"
)
WDPA_SITE_ID = 556326231
NATURAL_EARTH_LAND = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_land.geojson"
LAND_CLIP = (77.5, 7.5, 81.0, 11.0)  # region box + margin (lon_min, lat_min, lon_max, lat_max)


def dm(deg: int, minutes: float) -> float:
    return round(deg + minutes / 60.0, 6)


# (label, lat, lon) in degrees + decimal minutes, exactly as in the treaty texts.
# 1976 Art. 1 lists 4 m longitude as "79° 18'.2 N" — a typo in the source for E.
GULF_OF_MANNAR = [  # 1976 Art. 1, from position 1 m (= 1974 position 6) south-west
    ("1m", dm(9, 6.0), dm(79, 32.0)),
    ("2m", dm(9, 0.0), dm(79, 31.3)),
    ("3m", dm(8, 53.8), dm(79, 29.3)),
    ("4m", dm(8, 40.0), dm(79, 18.2)),
    ("5m", dm(8, 37.2), dm(79, 13.0)),
    ("6m", dm(8, 31.2), dm(79, 4.7)),
    ("7m", dm(8, 22.2), dm(78, 55.4)),
    ("8m", dm(8, 12.2), dm(78, 53.7)),
    ("9m", dm(7, 35.3), dm(78, 45.7)),
    ("10m", dm(7, 21.0), dm(78, 38.8)),
    ("11m", dm(6, 30.8), dm(78, 12.2)),
    ("12m", dm(5, 53.9), dm(77, 50.7)),
    ("13m", dm(5, 0.0), dm(77, 10.6)),
]
PALK = [  # 1974 Art. 1, Palk Strait to Adam's Bridge
    ("1", dm(10, 5.0), dm(80, 3.0)),
    ("2", dm(9, 57.0), dm(79, 35.0)),
    ("3", dm(9, 40.15), dm(79, 22.60)),
    ("4", dm(9, 21.80), dm(79, 30.70)),
    ("5", dm(9, 13.0), dm(79, 32.0)),
    ("6", dm(9, 6.0), dm(79, 32.0)),
]
BAY_OF_BENGAL = [  # 1976 Art. 2, from position 1 b (= 1974 position 1) north-east
    ("1b", dm(10, 5.0), dm(80, 3.0)),
    ("1ba", dm(10, 5.8), dm(80, 5.0)),
    ("1bb", dm(10, 8.4), dm(80, 9.5)),
    ("2b", dm(10, 33.0), dm(80, 46.0)),
    ("3b", dm(10, 41.7), dm(81, 2.5)),
    ("4b", dm(11, 2.7), dm(81, 56.0)),
    ("5b", dm(11, 16.0), dm(82, 24.4)),
    ("6b", dm(11, 26.6), dm(83, 22.0)),
]


def imbl_positions() -> list[tuple[str, float, float]]:
    """South-west → north-east: 13m … 1m (= 6), 5 … 1 (= 1b), 1ba … 6b. Shared points appear once."""
    south = list(reversed(GULF_OF_MANNAR))[:-1]  # 13m … 2m
    palk = list(reversed(PALK))  # 6 … 1
    north = BAY_OF_BENGAL[1:]  # 1ba … 6b
    return south + palk + north


def build_imbl() -> dict[str, object]:
    pts = imbl_positions()
    return {
        "type": "FeatureCollection",
        "name": "imbl",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": "imbl",
                    "name": "India–Sri Lanka maritime boundary (IMBL)",
                    "source": "Agreements of 26/28 June 1974 and 23 March 1976 (UN DOALOS treaty texts)",
                    "source_url": [TREATY_1974, TREATY_1976],
                    "positions": [p[0] for p in pts],
                },
                "geometry": {"type": "LineString", "coordinates": [[lon, lat] for _, lat, lon in pts]},
            }
        ],
    }


def build_mpa() -> dict[str, object]:
    r = httpx.get(
        WDPA_QUERY,
        params={
            "where": f"site_id={WDPA_SITE_ID}",
            "outFields": "site_id,name_eng,desig_eng,status_yr",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        },
        timeout=120,
    )
    r.raise_for_status()
    feat = r.json()["features"][0]
    g = shape(feat["geometry"])
    parts = g.geoms if isinstance(g, MultiPolygon) else [g]
    filled = unary_union([Polygon(p.exterior) for p in parts])
    return {
        "type": "FeatureCollection",
        "name": "mpa_gom",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": "mpa_gom",
                    "name": "Gulf of Mannar Marine National Park + eco-sensitive zone",
                    "source": f"WDPA site {WDPA_SITE_ID} ({feat['properties'].get('desig_eng')}, "
                    f"{feat['properties'].get('status_yr')}), holes filled",
                    "source_url": f"https://www.protectedplanet.net/{WDPA_SITE_ID}",
                    "licence": "WDPA terms of use (non-commercial); attribution UNEP-WCMC and IUCN",
                },
                "geometry": mapping(filled),
            }
        ],
    }


def build_land() -> dict[str, object]:
    """Natural Earth 1:10m land (public domain), clipped to the region: route search never crosses land."""
    from shapely.geometry import box

    r = httpx.get(NATURAL_EARTH_LAND, timeout=300, follow_redirects=True)
    r.raise_for_status()
    clip = box(*LAND_CLIP)
    parts = [shape(f["geometry"]).intersection(clip) for f in r.json()["features"]]
    land = unary_union([p for p in parts if not p.is_empty])
    return {
        "type": "FeatureCollection",
        "name": "land",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": "land",
                    "name": "Land (Natural Earth 1:10m), clipped to the region",
                    "source": "Natural Earth ne_10m_land",
                    "source_url": "https://www.naturalearthdata.com/downloads/10m-physical-vectors/",
                    "licence": "Public domain",
                },
                "geometry": mapping(land),
            }
        ],
    }


def main() -> None:
    out = find_config_dir().parent / "data" / "layers"
    out.mkdir(parents=True, exist_ok=True)
    for name, fc in (("imbl", build_imbl()), ("mpa_gom", build_mpa()), ("land", build_land())):
        (out / f"{name}.geojson").write_text(json.dumps(fc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {out / name}.geojson")


if __name__ == "__main__":
    main()
