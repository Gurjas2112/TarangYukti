"""Governance gate (Milestone 9): every governed file has a code owner and the version-bump checker runs."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def checker():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("check_governed", ROOT / "scripts" / "check_governed.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_governed_file_has_a_code_owner() -> None:
    mod = checker()
    rules = [
        ln.split()[0]
        for ln in (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#") and not ln.startswith("*")
    ]
    for path in [*mod.VERSIONED, "config/phrases/ta.yaml", "apps/agent/src/prompts/planner.md"]:
        assert mod.codeowners_cover(path, rules), path


def test_versioned_configs_declare_a_version() -> None:
    mod = checker()
    for path in mod.VERSIONED:
        assert mod.version_of((ROOT / path).read_text(encoding="utf-8")), path


def test_an_empty_range_passes() -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert checker().check(head, head) == []
