"""The seven tool-calling specialists the planner calls (spec Table 6-7). The Language agent runs as a graph
node before and after the planner (src/agents/language.py).

Each specialist is wrapped as a LangChain @tool (prompt §3: supervisor via tool-calling). They are deterministic
orchestrators over the FastMCP data tools: they call their tools in parallel and return a compact digest. No
specialist asks an LLM for a number, so every figure the planner sees comes from a ToolResult.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool

from .. import digest
from .base import Turn, call, gather, prompt, where

BoatType = Literal["non_motorised", "small_frp", "mechanised_trawler"]


def make_tools(turn: Turn) -> list[BaseTool]:
    ev = turn.evidence

    async def data_discovery() -> str:
        sources = [
            ("forecast", "Open-Meteo waves and wind", "online", "6 h"),
            ("warnings", "IMD, INCOIS and state alerts via NDMA SACHET", "online", "1 h"),
            ("sst", "NOAA sea-surface temperature", "online", "48 h"),
            ("chl", "NOAA-20 chlorophyll", "online", "48 h"),
            ("pfz", "INCOIS Potential Fishing Zone", "snapshot only", "24 h"),
            (
                "documents",
                "Acts, ban order, landings, safety procedures",
                "knowledge base",
                "validity windows",
            ),
        ]
        return ev.add(
            {
                "kind": "catalogue",
                "datasets": [{"id": i, "what": w, "access": a, "freshness_limit": f} for i, w, a, f in sources],
            }
        )

    async def weather_intel(lat: float | None = None, lon: float | None = None, hours: int = 12) -> str:
        la, lo = where(lat, lon)
        f, imd, incois, sdma = await gather(
            turn,
            ("marine_forecast", {"lat": la, "lon": lo, "hours": max(1, min(hours, 72))}),
            ("imd_warnings", {}),
            ("incois_alerts", {}),
            ("sdma_alerts", {}),
        )
        if f is None:
            return ev.add({"kind": "weather", "available": False, "errors": ev.errors[-4:]})
        return ev.add(digest.weather(f, [w for w in (imd, incois, sdma) if w is not None], hours))

    async def ocean_analytics(what: Literal["sst", "chlorophyll", "pfz"] = "sst") -> str:
        tool = {"sst": "sst_grid", "chlorophyll": "chl_grid", "pfz": "pfz_incois"}[what]
        r = await call(turn, tool, {})
        if r is None:
            return ev.add({"kind": what, "available": False})
        return ev.add(digest.pfz(r) if what == "pfz" else digest.grid(r, what))

    async def geospatial(
        lat: float | None = None,
        lon: float | None = None,
        to_lat: float | None = None,
        to_lon: float | None = None,
    ) -> str:
        la, lo = where(lat, lon)
        calls: list[tuple[str, dict[str, Any]]] = [("fence_check", {"lat": la, "lon": lo})]
        if to_lat is not None and to_lon is not None:
            calls.append(("geo_distance", {"lat1": la, "lon1": lo, "lat2": to_lat, "lon2": to_lon}))
        f, *rest = await gather(turn, *calls)
        out: dict[str, Any] = {"kind": "geo", "fence": digest.fence(f) if f else {"available": False}}
        if rest and rest[0]:
            out["distance"] = digest.distance(rest[0])
        return ev.add(out)

    async def knowledge(question: str) -> str:
        r = await call(turn, "kb_search", {"query": question})
        if r is None:
            return ev.add({"kind": "knowledge", "available": False})
        d = digest.knowledge(r)
        if r["data"].get("chunks"):
            ev.passages.update({c["marker"]: c["content"] for c in r["data"]["chunks"]})
        return ev.add(d)

    async def yukti(
        boat_type: BoatType | None = None,
        lat: float | None = None,
        lon: float | None = None,
        goal_lat: float | None = None,
        goal_lon: float | None = None,
        depart_at: str | None = None,
    ) -> str:
        la, lo = where(lat, lon)
        r = await call(
            turn,
            "yukti_evaluate",
            {
                "boat_type": boat_type or turn.boat_type,
                "lat": la,
                "lon": lo,
                "goal_lat": goal_lat,
                "goal_lon": goal_lon,
                "depart_at": depart_at,
            },
        )
        if r is None:
            return ev.add({"kind": "yukti", "available": False, "errors": ev.errors[-1:]})
        d = digest.yukti(r)
        ev.yukti.append(d)
        return ev.add(d)

    async def explain(answer_id: str | None = None) -> str:
        """Sea Signal card for the app from the latest verdict of this turn (the ledger was written by Yukti)."""
        y = next((d for d in reversed(ev.yukti) if answer_id in (None, d.get("answer_id"))), None)
        if y is None:
            return digest.dumps({"kind": "card", "available": False, "reason": "no verdict in this turn"})
        req = y["requested"] or {}
        card = {
            "kind": "card",
            "verdict": y["verdict"],
            "answer_id": y["answer_id"],
            "reasons": [f["id"] for f in req.get("failed", [])],
            "next_window": (y.get("earliest_window") or {}).get("depart"),
        }
        return digest.dumps(card)

    specs = [
        (data_discovery, "data_discovery"),
        (weather_intel, "weather_intel"),
        (ocean_analytics, "ocean_analytics"),
        (geospatial, "geospatial"),
        (knowledge, "knowledge"),
        (yukti, "yukti"),
        (explain, "explain"),
    ]
    return [
        StructuredTool.from_function(
            coroutine=fn,  # type: ignore[arg-type]
            name=name,
            description=prompt(name),
        )
        for fn, name in specs
    ]
