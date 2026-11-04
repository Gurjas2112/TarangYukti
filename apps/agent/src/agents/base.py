"""Shared pieces for the specialist agents: per-turn evidence, prompts, the home harbour."""

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from ty_common.settings import find_config_dir

from .. import digest
from ..gateway import Gateway, ToolError

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


@functools.cache
def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8").strip()


@functools.cache
def home_harbour() -> tuple[float, float]:
    qc = yaml.safe_load((find_config_dir() / "qc.yaml").read_text(encoding="utf-8"))
    h = qc["region"]["home_harbour"]
    return float(h["lat"]), float(h["lon"])


@dataclass
class Evidence:
    """Everything the specialists returned in one turn: digests for grounding, raw results for templates."""

    digests: list[dict[str, Any]] = field(default_factory=list)
    yukti: list[dict[str, Any]] = field(default_factory=list)  # yukti digests (template fallback, Simple mode)
    passages: dict[str, str] = field(default_factory=dict)  # marker → chunk text (citation check)
    errors: list[str] = field(default_factory=list)

    def add(self, d: dict[str, Any]) -> str:
        self.digests.append(d)
        return digest.dumps(d)

    def texts(self) -> list[str]:
        return [digest.dumps(d) for d in self.digests]


@dataclass
class Turn:
    gateway: Gateway
    evidence: Evidence
    boat_type: str = "small_frp"


async def call(turn: Turn, name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return await turn.gateway.call(name, args)
    except ToolError as e:
        turn.evidence.errors.append(str(e))
        return None


async def gather(turn: Turn, *calls: tuple[str, dict[str, Any]]) -> list[dict[str, Any] | None]:
    return list(await asyncio.gather(*(call(turn, n, a) for n, a in calls)))


def where(lat: float | None, lon: float | None) -> tuple[float, float]:
    """The given position, or the home harbour when the question names none."""
    if lat is None or lon is None:
        return home_harbour()
    return lat, lon
