"""`make kb-query Q="..."`: run kb_search once and print the cited passages."""

from __future__ import annotations

import asyncio
import sys

from .search import kb_search


def main() -> None:
    q = " ".join(sys.argv[1:]).strip()
    if not q:
        raise SystemExit('usage: make kb-query Q="your question"')
    r = asyncio.run(kb_search(q))
    d = r["data"]
    if d.get("available") is False:
        raise SystemExit(d["reason"])
    print(f"mode={d['mode']} relevant={d['relevant']} best_sim={d['best_sim']} english={d['english_query']!r}")
    for c in d["chunks"]:
        doc = c["document"]
        print(f"\n[{c['marker']}] sim={c['sim']} {doc['issuer']} · {doc['title']} (v{doc['version']})")
        print("    " + c["content"][:300].replace("\n", " "))
    for n in r["notes"]:
        print("note:", n)


if __name__ == "__main__":
    main()
