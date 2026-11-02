"""Live IMD/INCOIS alerts from NDMA SACHET (CAP 1.2). Fixtures are real alerts saved on 2026-11-02."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from tarangyukti.tools import cap, warnings
from tarangyukti.tools.alert_model import Warning_
from tarangyukti.tools.common import freeze

from .conftest import make_snapshot

FIX = Path(__file__).parent / "fixtures"
INCOIS_XML = (FIX / "cap_incois_storm_surge_via_sdma.xml").read_bytes()
IMD_XML = (FIX / "cap_imd_chennai_thunderstorm.xml").read_bytes()
B = "https://sachet.ndma.gov.in/cap_public_website/"

# a small square over the Gulf of Mannar near Rameswaram, in SACHET's "lat,lon" polygon format
GOM_POLYGON = b"<alert><polygon>9.1,79.1 9.1,79.3 9.3,79.3 9.3,79.1 9.1,79.1</polygon></alert>"
FAR_POLYGON = b"<alert><polygon>15.1,80.0 15.1,80.3 15.4,80.3 15.4,80.0 15.1,80.0</polygon></alert>"


def test_issuer_attribution() -> None:
    assert cap.issuer_of("IMD-Chennai") == "IMD"
    assert cap.issuer_of("Andhra-Pradesh-SDMA", "INCOIS,IN-1793611251003008_101,2026-11-02T14:50:19+05:30") == "INCOIS"
    assert cap.issuer_of("Tamil-Nadu-SDMA", "IMD,IN-1,2026-11-02") == "IMD"
    assert cap.issuer_of("Tamil-Nadu-SDMA") == "SDMA"
    assert cap.issuer_of("Some-Agency") is None


def test_parse_incois_relayed_by_sdma() -> None:
    w = cap.parse_cap(INCOIS_XML, "Andhra Pradesh SDMA", "https://x", None)
    assert w is not None
    assert w.issuer == "INCOIS"
    assert w.kind == "storm_surge"
    assert (w.cap_severity, w.severity) == ("Severe", "warning")
    assert w.title.startswith("For Severe Cyclonic Storm MURASU")  # the English <info> block
    assert w.valid_to == datetime(2026, 11, 3, 3, 0, tzinfo=UTC)  # 08:30 IST
    assert "Bapatla" in w.sectors and w.districts == []


def test_parse_imd_district_nowcast() -> None:
    w = cap.parse_cap(IMD_XML, "IMD Chennai", "https://x", None)
    assert w is not None
    assert (w.issuer, w.kind, w.severity) == ("IMD", "thunderstorm", "alert")
    assert w.districts == ["Ranipet", "Tirupathur", "Tiruvannamalai", "Viluppuram"]


def test_region_by_polygon_and_by_name() -> None:
    gom = cap.parse_polygons(GOM_POLYGON)
    far = cap.parse_polygons(FAR_POLYGON)
    w = cap.parse_cap(IMD_XML, "IMD Chennai", "https://x", gom)
    assert w is not None and cap.in_region(w)
    w2 = cap.parse_cap(IMD_XML, "IMD Chennai", "https://x", far)
    assert w2 is not None and not cap.in_region(w2)
    no_poly = cap.parse_cap(IMD_XML, "IMD Chennai", "https://x", None)
    assert no_poly is not None and not cap.in_region(no_poly)  # inland districts, no polygon
    named = no_poly.model_copy(update={"area_desc": "Ramanathapuram, Thoothukudi districts of Tamil Nadu"})
    assert cap.in_region(named)


def _mock_sachet(router: respx.MockRouter, polygon: bytes = GOM_POLYGON) -> None:
    router.get(B + "FetchAllAlertDetails").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"identifier": 111, "alert_source": "Tamil Nadu SDMA", "centroid": "79.2,9.2"},  # INCOIS relayed
                {"identifier": 222, "alert_source": "IMD Chennai", "centroid": "79.3,9.3"},
                {"identifier": 333, "alert_source": "IMD Delhi", "centroid": "77.2,28.6"},  # far: never opened
            ],
        )
    )
    router.get(B + "FetchXMLFile", params={"identifier": "111"}).mock(
        return_value=httpx.Response(200, content=INCOIS_XML)
    )
    router.get(B + "FetchXMLFile", params={"identifier": "222"}).mock(return_value=httpx.Response(200, content=IMD_XML))
    router.get(url__startswith=B + "FetchPolygonXMLFile").mock(return_value=httpx.Response(200, content=polygon))


async def test_incois_alerts_live(real_cap: None) -> None:
    freeze(datetime(2026, 11, 2, 12, 0, tzinfo=UTC))
    with respx.mock(assert_all_called=False) as router:
        _mock_sachet(router)
        far = router.get(B + "FetchXMLFile", params={"identifier": "333"})
        r = await warnings.incois_alerts()
        assert not far.called
    assert r["cache"] == "miss"
    assert r["source"] == "INCOIS (via NDMA SACHET CAP)"
    assert r["data"]["count"] == 1
    assert r["data"]["active"][0]["kind"] == "storm_surge"
    assert r["data"]["active"][0]["area"]["type"] in ("Polygon", "MultiPolygon")


async def test_imd_warnings_live_and_place_filter(real_cap: None) -> None:
    freeze(datetime(2026, 11, 2, 13, 45, tzinfo=UTC))  # 19:15 IST, inside the nowcast window
    with respx.mock(assert_all_called=False) as router:
        _mock_sachet(router)
        r = await warnings.imd_warnings()
        r2 = await warnings.imd_warnings("Ranipet")
        r3 = await warnings.imd_warnings("Ramanathapuram")
    assert r["data"]["count"] == 1 and r["data"]["active"][0]["office"] == "IMD Chennai"
    assert r2["data"]["count"] == 1
    assert r3["data"]["count"] == 0


async def test_expired_alert_not_active(real_cap: None) -> None:
    freeze(datetime(2026, 11, 3, 6, 0, tzinfo=UTC))  # after both alerts expired
    with respx.mock(assert_all_called=False) as router:
        _mock_sachet(router)
        r = await warnings.incois_alerts()
    assert r["data"]["count"] == 0


async def test_rss_fallback_when_active_list_fails(real_cap: None) -> None:
    freeze(datetime(2026, 11, 2, 12, 0, tzinfo=UTC))
    rss = b"""<rss><channel><item><guid>111</guid><author>controlroom@ndma.gov.in (Tamil Nadu SDMA)</author></item>
    <item><guid>999</guid><author>controlroom@ndma.gov.in (Uttarakhand SDMA)</author></item></channel></rss>"""
    with respx.mock(assert_all_called=False) as router:
        _mock_sachet(router)
        router.get(B + "FetchAllAlertDetails").mock(return_value=httpx.Response(503))
        router.get(B + "rss/rss_india.xml").mock(return_value=httpx.Response(200, content=rss))
        r = await warnings.incois_alerts()
    assert r["data"]["count"] == 1
    assert any("latest-100 RSS" in n for n in r["notes"])


async def test_sachet_down_falls_back_to_snapshot(real_cap: None, env: Path) -> None:
    make_snapshot(env)
    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith=B).mock(return_value=httpx.Response(503))
        r = await warnings.incois_alerts("Ramanathapuram")
    assert r["cache"] == "snapshot"
    assert r["confidence"] == "low"
    assert r["data"]["count"] == 1


async def test_sdma_own_alert_in_region_is_noted(real_cap: None) -> None:
    freeze(datetime(2026, 11, 2, 12, 0, tzinfo=UTC))
    own = INCOIS_XML.replace(b"<cap:references>INCOIS,", b"<cap:references>")
    with respx.mock(assert_all_called=False) as router:
        _mock_sachet(router)
        router.get(B + "FetchXMLFile", params={"identifier": "111"}).mock(return_value=httpx.Response(200, content=own))
        r = await warnings.incois_alerts()
    assert r["data"]["count"] == 0
    assert any("not attributed to IMD/INCOIS" in n for n in r["notes"])


async def test_capture_keeps_simulation(real_cap: None, env: Path) -> None:
    from tarangyukti import sim_warning

    store = make_snapshot(env)
    sim_warning.apply(store)
    freeze(datetime(2026, 11, 2, 12, 0, tzinfo=UTC))
    with respx.mock(assert_all_called=False) as router:
        _mock_sachet(router)
        await cap.capture(store, "INCOIS")
    ws = [Warning_.model_validate(w) for w in store.read("warnings_incois")["payload"]["warnings"]]
    assert {w.simulation for w in ws} == {True, False}
    assert any(w.kind == "storm_surge" for w in ws)


def test_hostile_xml_rejected() -> None:
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><alert>&b;</alert>'
    with pytest.raises(Exception):  # noqa: B017 — defusedxml refuses entity declarations
        cap.parse_polygons(bomb)
