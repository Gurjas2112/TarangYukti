"""Compact, IST-formatted summaries of ToolResults for the LLM.

The planner reads digests, never raw tool JSON, and the validator grounds every number of a reply against the
digest texts of the turn — so every figure a reply may use appears here exactly as it should be written
(times in IST as HH:MM, distances in km with one decimal, waves in m with one decimal).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))


def ist(iso: str | None) -> str | None:
    """'2026-11-03T19:00:00+00:00' → '00:30 on 4 Nov (IST)'."""
    if not iso:
        return None
    t = datetime.fromisoformat(iso).astimezone(IST)
    return f"{t:%H:%M} on {t.day} {t:%b} (IST)"


def r1(x: Any) -> Any:
    return round(float(x), 1) if isinstance(x, (int, float)) else x


def provenance(tr: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": tr.get("source"),
        "fetched": ist(tr.get("fetched_at")),
        "cache": tr.get("cache"),
        "confidence": tr.get("confidence"),
        "notes": tr.get("notes", []),
    }


def unavailable(tr: dict[str, Any]) -> bool:
    d = tr.get("data")
    return isinstance(d, dict) and d.get("available") is False


def weather(forecast: dict[str, Any], warnings: list[dict[str, Any]], hours: int = 12) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "weather"}
    if unavailable(forecast):
        out["forecast"] = {"available": False, "reason": forecast["data"].get("reason")}
    else:
        rows = forecast["data"].get("hours", [])[:hours]
        out["forecast"] = {
            "hours": [
                {
                    "time": ist(h["time"]),
                    "wave_m": r1(h.get("wave_m")),
                    "wind_kmh": r1(h.get("wind_kmh")),
                    "gust_kmh": r1(h.get("gust_kmh")),
                }
                for h in rows
            ],
            "max_wave_m": r1(max((h["wave_m"] for h in rows if h.get("wave_m") is not None), default=None)),
            "max_wind_kmh": r1(max((h["wind_kmh"] for h in rows if h.get("wind_kmh") is not None), default=None)),
            **provenance(forecast),
        }
    alerts = []
    for tr in warnings:
        if unavailable(tr):
            alerts.append({"source": tr.get("source"), "available": False})
            continue
        for w in [*tr["data"].get("active", []), *tr["data"].get("upcoming", [])]:
            alerts.append(
                {
                    "issuer": w["issuer"],
                    "event": w.get("event") or w["kind"],
                    "title": w["title"],
                    "from": ist(w["valid_from"]),
                    "until": ist(w["valid_to"]),
                    "simulation": w.get("simulation", False),
                }
            )
    out["official_warnings"] = alerts
    return out


def yukti(tr: dict[str, Any]) -> dict[str, Any]:
    d = tr["data"]

    def ev(e: dict[str, Any] | None) -> dict[str, Any] | None:
        if not e:
            return None
        failed = [x for x in e["ledger"] if x["kind"] == "hard" and not x["ok"]]
        return {
            "verdict": e["outcome"],
            "depart": ist(e["depart"]),
            "back_by": ist(e["return_at"]),
            "risk": r1(e["risk"]) if e.get("risk") is not None else None,
            "route_km": r1(e.get("route_km")),
            "failed": [
                {
                    "id": x["id"],
                    "name": x["name"],
                    "value": _v(x),
                    "detail": x["detail"],
                    "at": ist(x.get("at")),
                }
                for x in failed
            ],
            "soft_warnings": [
                {"id": x["id"], "name": x["name"], "detail": x["detail"]}
                for x in e["ledger"]
                if x["kind"] == "soft" and not x["ok"] and not x["unknown"]
            ],
        }

    return {
        "kind": "yukti",
        "verdict": d["verdict"],
        "boat_type": d["boat_type"],
        "as_of": ist(d["as_of"]),
        "requested": ev(d["requested"]),
        "earliest_window": ev(d.get("earliest_window")),
        "recommended": ev(d.get("recommended")),
        "answer_id": d.get("answer_id"),
        **provenance(tr),
    }


def _v(x: dict[str, Any]) -> Any:
    v = x.get("value")
    if isinstance(v, float):
        v = r1(v)
    return f"{v} {x['unit']}" if x.get("unit") and v not in (None, "unknown") else v


def fence(tr: dict[str, Any]) -> dict[str, Any]:
    d = tr["data"]
    return {
        "kind": "fence",
        "border_line_km": r1(d["imbl_km"]),
        "side": d["side"],
        "ring": d["ring"],
        "in_marine_park": d["in_mpa"],
        **provenance(tr),
    }


def distance(tr: dict[str, Any]) -> dict[str, Any]:
    d = tr["data"]
    return {"kind": "distance", "km": r1(d["km"]), "nm": r1(d["nm"]), "direction": d["direction"]}


def knowledge(tr: dict[str, Any]) -> dict[str, Any]:
    if unavailable(tr):
        return {"kind": "knowledge", "available": False, "reason": tr["data"].get("reason")}
    d = tr["data"]
    return {
        "kind": "knowledge",
        "relevant": d["relevant"],
        "mode": d["mode"],
        "passages": [
            {
                "marker": c["marker"],
                "chunk_id": c.get("chunk_id"),
                "issuer": c["document"]["issuer"],
                "title": c["document"]["title"],
                "valid_to": c["document"]["valid_to"],
                "text": c["content"],
            }
            for c in d["chunks"]
        ]
        if d["relevant"]
        else [],
        "notes": tr.get("notes", []),
    }


def grid(tr: dict[str, Any], label: str) -> dict[str, Any]:
    if unavailable(tr):
        return {"kind": label, "available": False, "reason": tr["data"].get("reason")}
    d = tr["data"]
    s = d["stats"]
    return {
        "kind": label,
        "unit": d["unit"],
        "data_time": ist(d["time"]),
        "age_hours": r1(d["age_hours"]),
        "min": r1(s["min"]),
        "mean": r1(s["mean"]),
        "max": r1(s["max"]),
        "cloud_masked_percent": round(100 * s["masked_fraction"]),
        **provenance(tr),
    }


def pfz(tr: dict[str, Any]) -> dict[str, Any]:
    if unavailable(tr):
        return {"kind": "pfz", "available": False, "reason": tr["data"].get("reason")}
    d = tr["data"]
    return {
        "kind": "pfz",
        "issued": ist(d["issued_at"]),
        "valid_to": ist(d["valid_to"]),
        "zones": [{"id": z["id"], "text": z["text"]} for z in d["zones"]],
        **provenance(tr),
    }


def dumps(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)
