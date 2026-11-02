from tarangyukti.cache import cached
from tarangyukti.server import mcp, ping

EXPECTED = {
    "marine_forecast",
    "imd_warnings",
    "incois_alerts",
    "pfz_incois",
    "sst_grid",
    "chl_grid",
    "fence_check",
    "geo_distance",
    "sdma_alerts",
    "yukti_evaluate",
    "route_safest",
    "ping",
}


def test_ping_is_a_tool_result() -> None:
    fn = getattr(ping, "fn", ping)
    out = fn()
    assert out["source"] == "tarangyukti"
    assert out["data"] == {"ok": True}


async def test_all_milestone2_tools_registered() -> None:
    tools = await mcp.list_tools() if hasattr(mcp, "list_tools") else await mcp.get_tools()
    names = {t.name for t in (tools.values() if isinstance(tools, dict) else tools)}
    assert names >= EXPECTED


async def test_tool_docstrings_state_units() -> None:
    tools = await mcp.list_tools() if hasattr(mcp, "list_tools") else await mcp.get_tools()
    by_name = {t.name: t for t in (tools.values() if isinstance(tools, dict) else tools)}
    assert "km" in (by_name["fence_check"].description or "")
    assert "°C" in (by_name["marine_forecast"].description or "")


def test_shared_cache_is_reexported() -> None:
    assert callable(cached)
