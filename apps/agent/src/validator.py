"""The validator (prompt §9, spec §6.4.2): every reply passes these checks or is rewritten once, then replaced by a
template from the ledger.

1. Numbers grounded: every number with a unit and every HH:MM time appears in a tool output of the turn.
2. Citations: every [Kn] is a retrieved passage and its quote is a verbatim span of it (else the sentence is
   dropped and counted as quote_dropped).
3. Language: the final reply is in the thread's language (script check).
4. Simple mode: no codes PFZ, IMBL, H1–H8.
Plus: "safe" never appears without "advisory".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ty_common.quotes import is_verbatim

NUM = re.compile(r"(?<![\w.-])\d{1,3}(?:[.,]\d+)?\s?(?:m|km|nm|°c|knots?|kmph|km/h|%|hrs?|h)?(?![\w])", re.I)
TIME = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")
MARKER = re.compile(r"\[K(\d+)\]")
CODES = re.compile(r"\b(PFZ|IMBL|H[1-8])\b")
SAFE = re.compile(r"\bsafe(ly)?\b", re.I)  # "safety" (as in "safety procedures") is fine
SENTENCE = re.compile(r"(?<=[.!?।])\s+")

# Unicode script ranges per language family (enough to tell the reply's script from the expected one)
SCRIPTS = {
    "Latn": r"[A-Za-z]",
    "Taml": r"[஀-௿]",
    "Deva": r"[ऀ-ॿ]",
    "Beng": r"[ঀ-৿]",
    "Telu": r"[ఀ-౿]",
    "Knda": r"[ಀ-೿]",
    "Mlym": r"[ഀ-ൿ]",
    "Gujr": r"[઀-૿]",
    "Guru": r"[਀-੿]",
    "Orya": r"[଀-୿]",
    "Arab": r"[؀-ۿ]",
    "Olck": r"[᱐-᱿]",
    "Mtei": r"[ꯀ-꯿]",
}


def canon(s: str) -> str:
    return re.sub(r"\s", "", s.lower()).replace(",", ".")


def ungrounded(answer: str, tool_texts: list[str]) -> list[str]:
    """Numbers and times in the answer that no tool output of the turn contains. Single digits pass.

    Times (HH:MM) are matched first and removed, so "06:30" is checked as one time, not as the number "06".
    """
    allowed_times = {m.group() for t in tool_texts for m in TIME.finditer(t)}
    allowed = {canon(m.group()) for t in tool_texts for m in NUM.finditer(TIME.sub(" ", t))}
    allowed |= {re.sub(r"[^\d.]", "", a) for a in allowed}  # a bare number matches the same number with a unit
    text = MARKER.sub("", answer)  # [K3] markers are not numbers
    bad = [m.group() for m in TIME.finditer(text) if m.group() not in allowed_times]
    for m in NUM.finditer(TIME.sub(" ", text)):
        n = m.group().strip()
        c = canon(n)
        if re.fullmatch(r"\d", n) or c in allowed or re.sub(r"[^\d.]", "", c) in allowed:
            continue
        bad.append(n)
    return bad


def check_citations(text: str, citations: list[dict[str, str]], passages: dict[str, str]) -> tuple[str, list[str]]:
    """Drop every sentence whose [Kn] marker was not retrieved or has no verbatim quote. Returns (text, dropped)."""
    verified = {
        c["marker"].strip("[] ")
        for c in citations
        if c.get("marker", "").strip("[] ") in passages
        and is_verbatim(passages[c["marker"].strip("[] ")], c.get("quote", ""))
    }
    kept, dropped = [], []
    for sentence in SENTENCE.split(text.strip()):
        markers = {f"K{m}" for m in MARKER.findall(sentence)}
        if markers and not markers <= verified:
            dropped.extend(sorted(markers - verified))
            continue
        kept.append(sentence)
    return " ".join(kept).strip(), dropped


def script_of(lang: str) -> str:
    from .agents.language import script_for

    return script_for(lang)


def language_ok(text: str, lang: str) -> bool:
    """The reply is mostly in the expected script (numbers, codes and quotes may be Latin)."""
    expected = script_of(lang)
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return True
    pat = re.compile(SCRIPTS.get(expected, SCRIPTS["Latn"]))
    share = sum(1 for ch in letters if pat.match(ch)) / len(letters)
    return share >= (0.6 if expected == "Latn" else 0.3)


@dataclass
class Check:
    ungrounded: list[str] = field(default_factory=list)
    quote_dropped: list[str] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)
    unsafe_wording: bool = False
    empty: bool = False
    text: str = ""

    @property
    def ok(self) -> bool:
        return not (self.ungrounded or self.codes or self.unsafe_wording or self.empty)

    def problems(self) -> list[str]:
        out = []
        if self.ungrounded:
            out.append(f"numbers not in any tool output: {', '.join(self.ungrounded)}")
        if self.quote_dropped:
            out.append(f"citations without a verbatim quote from a retrieved passage: {', '.join(self.quote_dropped)}")
        if self.codes:
            out.append(f"codes not allowed in Simple mode: {', '.join(sorted(set(self.codes)))}")
        if self.unsafe_wording:
            out.append('the word "safe" without "advisory only"')
        if self.empty:
            out.append("no answer text left after the checks")
        return out


def validate(
    text: str, citations: list[dict[str, str]], tool_texts: list[str], passages: dict[str, str], mode: str
) -> Check:
    cleaned, dropped = check_citations(text, citations, passages)
    c = Check(quote_dropped=dropped, text=cleaned)
    c.ungrounded = ungrounded(cleaned, tool_texts)
    if mode != "expert":
        c.codes = CODES.findall(cleaned)
    c.unsafe_wording = bool(SAFE.search(cleaned)) and "advisory" not in cleaned.lower()
    c.empty = not cleaned.strip()
    return c
