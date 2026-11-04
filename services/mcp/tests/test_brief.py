"""Simple-mode sea card (Milestone 6): approved phrases only, never a code, reasons and ribbon from the engine."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

import pytest
from ty_common.phrases import phrases

from tarangyukti import brief
from tarangyukti.yukti import facts

from .yukti_helpers import T0, Sea, make_ctx, warning

CODE = re.compile(r"\b(PFZ|IMBL|H[1-8]|S[1-5])\b")


def texts(card: dict[str, Any]) -> list[str]:
    out = [card["headline"], *card["why"], card["border"]["text"], card["footer"], card["speak"]]
    if card["spot"]:
        out.append(card["spot"]["text"])
    if card["stale"]:
        out.append(card["stale"])
    return out


@pytest.fixture
def sea(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"ctx": make_ctx()}

    async def gather(boat_type: str, start: str) -> tuple[Any, list[dict[str, Any]]]:
        return state["ctx"], []

    monkeypatch.setattr(facts, "gather", gather)
    return state


async def test_calm_sea_card(sea: dict[str, Any]) -> None:
    card = await brief.sea_brief("rameswaram", "small_frp", "en-IN")
    p, _ = phrases("en-IN")
    assert card["verdict"] == "GO" and card["headline"] == p["verdict"]["GO"]
    assert card["why"] == [] and card["window"] is not None
    assert len(card["ribbon"]) == 24 and {r["verdict"] for r in card["ribbon"]} <= {"GO", "CAUTION", "NO-GO"}
    assert re.fullmatch(r"\d{2}:\d{2}", card["ribbon"][0]["time"])
    assert card["footer"] == p["footer"] and card["speak"].endswith(p["footer"])
    assert not any(CODE.search(t) for t in texts(card))


async def test_warning_gives_no_go_with_plain_reason(sea: dict[str, Any]) -> None:
    sea["ctx"] = make_ctx(warnings=[warning(T0 - timedelta(hours=1), 6, wid="INCOIS-HW-9")])
    card = await brief.sea_brief("rameswaram", "small_frp", "en-IN")
    assert card["verdict"] == "NO-GO"
    assert card["headline"].startswith("Don't go today.")
    assert any("official" in w for w in card["why"])
    assert card["window"] is not None  # the warning ends after 5 h, so a later departure passes
    assert card["ribbon"][0]["verdict"] == "NO-GO"
    assert not any(CODE.search(t) for t in texts(card))


async def test_high_waves_reason_names_the_time(sea: dict[str, Any]) -> None:
    sea["ctx"] = make_ctx(weather=Sea(wave_m=2.0))
    card = await brief.sea_brief("rameswaram", "small_frp", "en-IN")
    assert card["verdict"] == "NO-GO" and card["window"] is None
    assert card["headline"].endswith(phrases("en-IN")[0]["no_window"] + ".")
    assert any(w.startswith("Waves get too high after") for w in card["why"])
    assert all(r["verdict"] == "NO-GO" for r in card["ribbon"])


async def test_card_is_cached_per_inputs(sea: dict[str, Any]) -> None:
    a = await brief.sea_brief("rameswaram", "small_frp", "en-IN")
    b = await brief.sea_brief("rameswaram", "small_frp", "en-IN")
    assert a == b
    c = await brief.sea_brief("rameswaram", "mechanised_trawler", "en-IN")
    assert c["boat_type"] == "mechanised_trawler"


async def test_unknown_harbour_rejected(sea: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        await brief.sea_brief("atlantis", "small_frp", "en-IN")


def test_direction_words() -> None:
    assert brief.direction_key(9.0, 79.0, 9.5, 79.0) == "north"
    assert brief.direction_key(9.0, 79.0, 8.7, 79.3) == "south_east"
    assert brief.direction_key(9.0, 79.0, 9.0, 78.5) == "west"


def test_spot_uses_nearest_pfz_point() -> None:
    ctx = make_ctx()
    ctx.pfz_points = [(9.0, 79.6), (9.10, 79.35)]
    s = brief.spot(ctx, 9.288, 79.313, phrases("en-IN")[0])
    assert s is not None and s["distance_km"] == 21 and s["text"] == "Fish likely 21 km south."
