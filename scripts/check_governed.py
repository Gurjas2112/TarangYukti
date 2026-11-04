"""Governance gate (prompt §12, spec §9.5): a governed file may not change without its version bump or release note.

- config/{constraints,boats,qc,sources,languages,aliases,harbours,governance}.yaml → its `version:` value changes
- config/phrases/*.yaml, apps/agent/src/prompts/*, ORCA_MODEL / EMBED_MODEL in .env.example → docs/releases.md changes
- every governed path must be covered by .github/CODEOWNERS

    python scripts/check_governed.py <base-ref> [<head-ref>]     # CI: the PR base, or HEAD~1 on main
Exit 1 with the reasons when the gate fails. Standard library only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONED = [f"config/{n}.yaml" for n in ("constraints", "boats", "qc", "sources", "languages", "aliases",
                                         "harbours", "governance")]
NEEDS_NOTE = ("config/phrases/", "apps/agent/src/prompts/")
MODEL_KEYS = re.compile(r"^[+-](ORCA_MODEL|EMBED_MODEL|ORCA_PLANNER_EFFORT|RAG_MIN_SIM)=", re.M)
VERSION = re.compile(r"^version:\s*(\S+)", re.M)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def show(ref: str, path: str) -> str | None:
    try:
        return git("show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return None


def version_of(text: str | None) -> str | None:
    m = VERSION.search(text or "")
    return m.group(1) if m else None


def codeowners_cover(path: str, rules: list[str]) -> bool:
    for r in rules:
        r = r.lstrip("/")
        if r.endswith("/") and path.startswith(r) or path == r:
            return True
    return False


def check(base: str, head: str) -> list[str]:
    changed = [p for p in git("diff", "--name-only", f"{base}..{head}").splitlines() if p]
    problems: list[str] = []
    for path in VERSIONED:
        if path in changed:
            old, new = version_of(show(base, path)), version_of(show(head, path))
            if new is None:
                problems.append(f"{path}: needs a `version:` line")
            elif old is not None and old == new:
                problems.append(f"{path} changed but its version stayed {old}: bump `version:` and say why in the file")
    noted = "docs/releases.md" in changed
    for path in changed:
        if path.startswith(NEEDS_NOTE) and not noted:
            problems.append(f"{path} changed: add a line to docs/releases.md (what, why, evaluation, approver)")
    if ".env.example" in changed and MODEL_KEYS.search(git("diff", f"{base}..{head}", "--", ".env.example")) and not noted:
        problems.append("model settings changed in .env.example: record the change in docs/releases.md")
    rules = [ln.split()[0] for ln in (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#") and not ln.startswith("*")]
    for path in [*VERSIONED, "config/phrases/en.yaml", "apps/agent/src/prompts/planner.md", "kb/sources/manifest.yaml"]:
        if (ROOT / path).exists() and not codeowners_cover(path, rules):
            problems.append(f"{path} has no code owner in .github/CODEOWNERS")
    return sorted(set(problems))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: check_governed.py <base-ref> [<head-ref>]")
    base, head = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    problems = check(base, head)
    for p in problems:
        print(f"::error::{p}")
    if problems:
        raise SystemExit(1)
    print("governance gate: ok")


if __name__ == "__main__":
    main()
