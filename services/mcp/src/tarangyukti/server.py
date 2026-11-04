"""FastMCP server (streamable HTTP on :8001/mcp) with the data tools.

Every tool returns a ToolResult (data, source, source_url, fetched_at, valid_at, confidence, cache, notes).
Milestone 3 added yukti_evaluate and route_safest; Milestone 4 added kb_search.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastmcp import FastMCP
from ty_common.models import ToolResult

from . import brief
from .rag import search as rag_search
from .tools import geo, grids, marine, warnings, yukti_tools

mcp = FastMCP("tarangyukti")

for fn in (
    marine.marine_forecast,
    warnings.imd_warnings,
    warnings.incois_alerts,
    warnings.sdma_alerts,
    warnings.pfz_incois,
    grids.sst_grid,
    grids.chl_grid,
    geo.fence_check,
    geo.geo_distance,
    yukti_tools.yukti_evaluate,
    yukti_tools.route_safest,
    rag_search.kb_search,
    brief.sea_brief,
):
    mcp.tool(fn)


@mcp.tool
def ping() -> dict[str, object]:
    """Health probe. Returns the server time (UTC). No units, no limits."""
    return ToolResult(
        data={"ok": True},
        source="tarangyukti",
        source_url="urn:tarangyukti:ping",
        fetched_at=datetime.now(UTC),
        confidence="high",
    ).model_dump(mode="json")


def main() -> None:
    mcp.run(transport="http", host="127.0.0.1", port=8001, path="/mcp")


if __name__ == "__main__":
    main()
