"""Walkthrough capture scenarios (spec §17.14.3): put the laptop backend into the state a flow needs.

Only when ENV=local and CAPTURE_SCENARIOS=1: anywhere else `current()` is always "normal", so no scenario can
ever affect Tier 1 (and channels answers 404 for the endpoint that sets one). The scenario lives in one small
file, data/capture/scenario.json, because it has to reach three processes (channels, mcp, agent). Capture
runs set CACHE_DISABLED=1 so a cached result never outlives a scenario change.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Literal, get_args

from .settings import find_config_dir, get_settings

Scenario = Literal[
    "normal",
    "brief-now",
    "simulated-warning",
    "no-safe-window",
    "stale-data",
    "llm-offline",
    "kill-switch-chat",
    "fault-next-request",
    "update-required",
]
NAMES: tuple[str, ...] = get_args(Scenario)
_cache: tuple[float, float, str] = (0.0, -1.0, "normal")  # (checked at, file mtime, name)


def enabled() -> bool:
    s = get_settings()
    return s.env == "local" and s.capture_scenarios


def path() -> Path:
    base = os.environ.get("TY_DATA_DIR")
    return (Path(base) if base else find_config_dir().parent / "data") / "capture" / "scenario.json"


def current() -> str:
    """The active scenario ("normal" unless capture is enabled and one is set). Re-read at most every 0.5 s."""
    global _cache
    if not enabled():
        return "normal"
    checked, mtime, name = _cache
    if time.monotonic() - checked < 0.5:
        return name
    p = path()
    try:
        m = p.stat().st_mtime
        if m != mtime:
            raw = json.loads(p.read_text(encoding="utf-8")).get("name", "normal")
            name = raw if raw in NAMES else "normal"
            mtime = m
    except FileNotFoundError:
        name, mtime = "normal", -1.0
    except (OSError, ValueError):
        name = "normal"
    _cache = (time.monotonic(), mtime, name)
    return name


def set_scenario(name: str) -> None:
    if not enabled():
        raise PermissionError("capture scenarios are disabled")
    if name not in NAMES:
        raise ValueError(f"unknown scenario {name!r}; one of {NAMES}")
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"name": name, "at": time.time()}), encoding="utf-8")
    global _cache
    _cache = (0.0, -1.0, "normal")


def active(name: str) -> bool:
    return current() == name
