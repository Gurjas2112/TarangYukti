"""Start ty-agent. On Windows, uvicorn would create a ProactorEventLoop, which async psycopg cannot use, so the
server runs on a selector loop instead. On Linux (WSL, containers) this is the same as `uvicorn server:app`.

    uv run python serve.py [--port 8123] [--host 127.0.0.1]
"""

from __future__ import annotations

import argparse
import asyncio
import selectors
import sys

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser(prog="serve.py")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8123)
    a = ap.parse_args()
    server = uvicorn.Server(uvicorn.Config("server:app", host=a.host, port=a.port, loop="none", workers=1))
    if sys.platform == "win32":
        asyncio.run(server.serve(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
