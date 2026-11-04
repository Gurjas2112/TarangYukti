"""Calls to the FastMCP data tools (ty-mcp) through langchain-mcp-adapters. Tests use FakeGateway."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from ty_common.settings import get_settings


class ToolError(Exception):
    """The tool server is unreachable or the tool refused the input."""


class Gateway(Protocol):
    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]: ...


class MCPGateway:
    def __init__(self, url: str | None = None) -> None:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        self.client = MultiServerMCPClient(
            {"tarangyukti": {"transport": "streamable_http", "url": url or get_settings().mcp_url}}
        )

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        clean = {k: v for k, v in args.items() if v is not None}
        try:
            async with self.client.session("tarangyukti") as s:
                r = await s.call_tool(name, clean)
        except Exception as e:  # network, protocol: the specialist reports the tool as unavailable
            raise ToolError(f"{name}: tool server unavailable ({type(e).__name__})") from e
        if r.isError:
            text = " ".join(getattr(c, "text", "") for c in r.content)
            raise ToolError(f"{name}: {text[:300]}")
        if r.structuredContent:
            data: dict[str, Any] = r.structuredContent
            inner = data.get("result", data)
            return inner if isinstance(inner, dict) else {"result": inner}
        text = "".join(getattr(c, "text", "") for c in r.content)
        out: dict[str, Any] = json.loads(text)
        return out


class FakeGateway:
    """Test double: tool name → result dict or a function of the arguments."""

    def __init__(self, results: dict[str, dict[str, Any] | Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]]):
        self.results = results
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, args))
        r = self.results.get(name)
        if r is None:
            raise ToolError(f"{name}: not available in this test")
        if callable(r):
            return await r(args)
        return r
