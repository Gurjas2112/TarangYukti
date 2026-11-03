from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from ty_common import aliases, quotes


def test_every_alias_maps_to_exactly_one_slug() -> None:
    tbl = aliases.table()  # raises on any alias claimed by two slugs
    for slug, t in aliases.terms().items():
        for spelling in [slug, t.get("name", slug), *t.get("aliases", [])]:
            assert tbl[aliases.norm(str(spelling))] == slug


def test_canonical_spellings() -> None:
    assert aliases.canonical("Rameshwaram") == "rameswaram"
    assert aliases.canonical("  ராமேஸ்வரம் ") == "rameswaram"
    assert aliases.canonical("BORDER LINE") == "imbl"
    assert aliases.canonical("vanjiram") == "seer-fish"
    assert aliases.canonical("unknown thing") is None


def test_topics_and_expansion() -> None:
    assert aliases.find_topics("The 61-day ban near the border line") == ["fishing-ban", "imbl"]
    assert aliases.find_topics("bordering states") == []  # word-bounded for Latin script
    assert "Seer fish" in aliases.expand_query("vanjiram ban")


def test_quote_exact_and_formatting_variants() -> None:
    chunk = "The uniform ban on fishing for 61 days is implemented annually by the Department of Fisheries."
    assert quotes.is_verbatim(chunk, "ban on fishing for 61 days")
    assert quotes.is_verbatim(chunk, "ban  on" + chr(10) + "fishing   for 61 days")
    assert quotes.is_verbatim(chunk, "the" + chr(0xA0) + "Department of Fisheries.")  # no-break space
    assert quotes.is_verbatim('The "uniform ban" on fishing', "“uniform ban” on fishing")


def test_quote_paraphrase_and_stitching_rejected() -> None:
    chunk = "The uniform ban on fishing for 61 days is implemented annually by the Department of Fisheries."
    assert not quotes.is_verbatim(chunk, "ban on fishing for 60 days")  # changed number
    assert not quotes.is_verbatim(chunk, "uniform ban implemented annually")  # stitched
    assert not quotes.is_verbatim(chunk, "61 days")  # too short to prove anything


@given(st.text(min_size=12, max_size=60), st.text(max_size=40), st.text(max_size=40))
def test_any_exact_span_is_accepted(span: str, before: str, after: str) -> None:
    if len(quotes.normalise(span)) >= quotes.MIN_CHARS:
        assert quotes.is_verbatim(before + " " + span + " " + after, span)
