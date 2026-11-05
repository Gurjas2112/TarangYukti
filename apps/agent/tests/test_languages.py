"""No language is built in (spec §6.5): no code path defaults to a fixed language, and detection only
switches when confident."""

from __future__ import annotations

import re
from pathlib import Path

from src.agents import language

ROOT = Path(__file__).resolve().parents[3]
CODE = [ROOT / "apps" / "agent", ROOT / "services", ROOT / "packages" / "ty-common" / "src"]
# A language code used as a *default*: dict.get("lang", "xx-IN"), a parameter default, or `or "xx-IN"`.
DEFAULT = re.compile(
    r"""(get\(\s*["']lang(uage)?["']\s*,\s*["'][a-z]{2,3}-IN["']|lang(uage)?\s*:\s*str\s*=\s*["'][a-z]{2,3}-IN["']"""
    r"""|\bor\s+["'][a-z]{2,3}-IN["'])"""
)


def test_no_hard_coded_default_language() -> None:
    hits = []
    for base in CODE:
        for p in base.rglob("*.py"):
            if any(part in {".venv", "tests", "__pycache__"} for part in p.parts):
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if DEFAULT.search(line):
                    hits.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()}")
    assert hits == []


def test_detection_and_stored_choice() -> None:
    assert language.choose(None, None, "Can I go to sea?") == "en-IN"  # Latin script, nothing stored
    assert language.choose(None, "ml-IN", "ok") == "ml-IN"  # a short Latin reply keeps the stored language
    assert language.choose(None, "ml-IN", "நாளை கடலுக்குப் போகலாமா?") == "ta-IN"  # clear Tamil script switches
    assert language.choose("gu-IN", "ta-IN", "hello") == "gu-IN"  # an explicit choice always wins


def test_number_check_ignores_units_and_leading_zeros_but_not_values() -> None:
    n = language._numbers
    assert n("warns at 5 km, leave at 05:30 [K4]") == n("5 கி.மீ தூரத்தில் … 5:30 [K4]")
    assert n("2.4 m") != n("2.6 m")
    assert n("leave at 05:30") != n("leave at 06:30")
    assert n("[K3] [K4]") != n("[K3]")  # a dropped citation marker is a change
