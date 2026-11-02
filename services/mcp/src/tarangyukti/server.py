"""FastMCP server (streamable HTTP on :8001/mcp). Data tools arrive in Milestone 2."""

from __future__ import annotations

from datetime import UTC, datetime

from fastmcp import FastMCP
from ty_common.models import ToolResult

mcp = FastMCP("tarangyukti")


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
