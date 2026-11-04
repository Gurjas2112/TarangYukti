"""Validator and language checks (prompt §16 Grounding / Languages)."""

from __future__ import annotations

import pytest

from src import templates, validator
from src.agents import language
from src.digest import ist


def test_invented_number_rejected() -> None:
    assert validator.ungrounded("Waves will reach 2.7 m by noon.", ['{"max_wave_m": 0.7}']) == ["2.7 m"]


def test_times_and_single_digits() -> None:
    tools = ['{"depart": "05:30 on 4 Nov (IST)"}']
    assert validator.ungrounded("Leave at 05:30 on step 2.", tools) == []
    assert validator.ungrounded("Leave at 06:30.", tools) == ["06:30"]


def test_number_with_or_without_unit() -> None:
    tools = ['{"border_line_km": 22.8}']
    assert validator.ungrounded("The border is 22.8 km away.", tools) == []
    assert validator.ungrounded("The border is 22.9 km away.", tools) == ["22.9 km"]


def test_markers_are_not_numbers() -> None:
    assert validator.ungrounded("The ban is in the order [K3].", []) == []


def test_fake_marker_removed() -> None:
    text, dropped = validator.check_citations("Fact one [K9]. Fact two.", [], {"K1": "x" * 40})
    assert text == "Fact two." and dropped == ["K9"]


def test_codes_blocked_in_simple_mode_only() -> None:
    simple = validator.validate("Stay 5 km from the IMBL (H2).", [], ['{"x": "5 km"}'], {}, "simple")
    assert not simple.ok and set(simple.codes) == {"IMBL", "H2"}
    expert = validator.validate("Stay 5 km from the IMBL (H2).", [], ['{"x": "5 km"}'], {}, "expert")
    assert expert.ok


def test_safe_needs_advisory() -> None:
    assert validator.validate("It is safe to go.", [], [], {}, "simple").unsafe_wording
    assert not validator.validate(
        "GO — no constraint violated, advisory only. It is safe.", [], [], {}, "simple"
    ).unsafe_wording
    assert not validator.validate("Read the safety procedure.", [], [], {}, "simple").unsafe_wording


def test_language_check() -> None:
    assert validator.language_ok("நாளை கடலுக்குப் போக வேண்டாம். 22.8 km", "ta-IN")
    assert not validator.language_ok("Do not go to sea tomorrow.", "ta-IN")
    assert validator.language_ok("Do not go to sea tomorrow.", "en-IN")


def test_language_choice() -> None:
    assert language.choose(None, None, "நாளை காலை கடலுக்குப் போகலாமா?") == "ta-IN"
    assert language.choose("ml-IN", None, "hello") == "ml-IN"
    assert language.choose(None, "ta-IN", "ok") == "ta-IN"  # kept from thread state
    assert language.choose(None, None, "Can I go?") == "en-IN"


async def test_translation_skipped_for_english_and_numbers_guarded(monkeypatch: object) -> None:
    assert await language.translate("Hello 22.8 km", "en-IN") == ("Hello 22.8 km", None)
    assert language._numbers("22.8 km at 05:30") == language._numbers("22.8km at 05:30")
    assert language._numbers("22.8 km") != language._numbers("22.6 km")


def test_sentence_split_respects_limit() -> None:
    parts = language.split_sentences("A long sentence. " * 300, limit=2000)
    assert all(len(p) <= 2000 for p in parts) and len(parts) > 1


def test_templates_cover_every_hard_constraint() -> None:
    p, used = templates.phrases("en-IN")
    assert used == "en-IN"
    assert {f"H{i}" for i in range(1, 9)} <= set(p["why"])


def test_unknown_language_falls_back_to_english_phrases() -> None:
    _, used = templates.phrases("xx-IN")  # no phrase file at all
    assert used == "en-IN"


def test_live_uses_only_approved_phrase_files(monkeypatch: pytest.MonkeyPatch) -> None:
    from ty_common import phrases as ph
    from ty_common.settings import get_settings

    monkeypatch.setattr(get_settings(), "env", "live")
    ph.load.cache_clear()
    try:
        with pytest.raises(RuntimeError):  # English is still a draft too, so nothing may be served in live
            templates.phrases("ta-IN")
    finally:
        ph.load.cache_clear()


def test_ist_format() -> None:
    assert ist("2026-11-03T19:00:00+00:00") == "00:30 on 4 Nov (IST)"
