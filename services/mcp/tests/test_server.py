from tarangyukti.cache import cached
from tarangyukti.server import mcp, ping


def test_ping_is_a_tool_result() -> None:
    fn = getattr(ping, "fn", ping)
    out = fn()
    assert out["source"] == "tarangyukti"
    assert out["data"] == {"ok": True}
    assert out["cache"] == "miss"


def test_shared_cache_is_reexported() -> None:
    assert callable(cached)
    assert mcp.name == "tarangyukti"
