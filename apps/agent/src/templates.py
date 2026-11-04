"""Replies assembled from approved phrases (config/phrases/<lang>.yaml) — Simple mode, button flows and the
fallback when the LLM is unavailable or its draft fails the validator twice. The LLM never writes these sentences.

A phrase file is used for a language when it exists (and, with ENV=live, is approved); otherwise English.
Slot values come only from Yukti digests (verdict times already formatted in IST).
"""

from __future__ import annotations

from typing import Any

from ty_common.phrases import phrases, phrases_version

__all__ = ["cannot_verify", "footer", "needs_network", "nothing_found", "phrases", "phrases_version", "verdict"]


def footer(lang: str) -> str:
    return str(phrases(lang)[0]["footer"])


def _time(s: str | None) -> str:
    return s or "—"


def verdict(y: dict[str, Any], lang: str) -> str:
    """'Don't go today. Next good time: …' + one reason per failed hard constraint (no codes)."""
    p, _ = phrases(lang)
    req = y.get("requested") or {}
    nxt = (y.get("earliest_window") or {}).get("depart")
    v = y["verdict"]
    if v == "NO-GO":
        head = p["verdict"]["NO-GO"].format(next_window=_time(nxt) if nxt else "none in the next 24 hours")
    elif v == "CAUTION":
        head = p["verdict"]["CAUTION"].format(back_by=_time(req.get("back_by")))
    else:
        head = p["verdict"]["GO"]
    reasons = []
    for f in req.get("failed", []):
        tpl = p.get("why", {}).get(f["id"])
        if not tpl:
            continue
        detail = f.get("detail") or ""
        reasons.append(
            tpl.format(
                time=_time(f.get("at") or req.get("depart")),
                issuer=detail.split(" ")[0] if detail else "official",
                warning_name=f.get("value") or detail,
                distance_km=f.get("value") or "",
            )
        )
    return " ".join([head, *dict.fromkeys(reasons)])


def chat_paused(lang: str) -> str:
    return str(phrases(lang)[0].get("chat_paused") or phrases("en-IN")[0]["chat_paused"])


def needs_network(lang: str) -> str:
    return str(phrases(lang)[0]["needs_network"])


def cannot_verify(lang: str) -> str:
    return str(phrases(lang)[0]["cannot_verify"])


def nothing_found(lang: str, source: str = "Department of Fisheries, INCOIS or IMD") -> str:
    return str(phrases(lang)[0]["nothing_found"]).format(source=source)
