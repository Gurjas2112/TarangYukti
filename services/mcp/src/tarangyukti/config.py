"""Parsed YAML config, loaded once per process (cache namespace `conf`, L1 only, spec Table 6-15)."""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

import yaml
from ty_common.settings import find_config_dir


@functools.cache
def load(name: str) -> dict[str, Any]:
    data = yaml.safe_load((find_config_dir() / name).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"config/{name} must be a mapping")
    return data


def sources() -> dict[str, Any]:
    return load("sources.yaml")


def qc() -> dict[str, Any]:
    return load("qc.yaml")


def constraints() -> dict[str, Any]:
    return load("constraints.yaml")


def endpoint(name: str) -> dict[str, Any]:
    ep: dict[str, Any] = sources()["endpoints"][name]
    return ep


def ttl(kind: str) -> int:
    return int(sources()["cache_ttl_s"][kind])


def data_dir() -> Path:
    """`TY_DATA_DIR`, else `<repo>/data` (layers are committed there; snapshots are git-ignored)."""
    env = os.environ.get("TY_DATA_DIR")
    return Path(env) if env else find_config_dir().parent / "data"
