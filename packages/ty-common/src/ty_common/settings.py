"""One settings object per process, read from the environment and the repo-root .env (prompt §5)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path | None:
    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidate = parent / ".env"
        if candidate.is_file() and (parent / "config").is_dir():
            return candidate
    return None


def find_config_dir() -> Path:
    """`ORCA_CONFIG_DIR` (set in Docker images) or the nearest `config/` directory upwards."""
    import os

    env = os.environ.get("ORCA_CONFIG_DIR")
    if env:
        return Path(env)
    for parent in [Path.cwd(), *Path.cwd().parents]:
        if (parent / "config" / "constraints.yaml").is_file():
            return parent / "config"
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "constraints.yaml").is_file():
            return parent / "config"
    raise FileNotFoundError("config/ directory not found; set ORCA_CONFIG_DIR")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,  # "KEY=" in .env means unset, not an empty secret
    )

    env: Literal["local", "ci", "preview", "live"] = "local"

    # Walkthrough capture (spec §17.14.3): laptop only, never set in Tier 1
    capture_scenarios: bool = False
    capture_token: SecretStr | None = None

    # Supabase
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_jwks_url: str | None = None
    database_url: SecretStr | None = None
    worker_database_url: SecretStr | None = None
    agent_database_url: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_db_url: SecretStr | None = None  # admin: migrations and role setup only, never services

    # LLM
    google_api_key: SecretStr | None = None
    orca_model: str = "gemini-3.8-flash"
    llm_timeout_s: float = 20.0

    # RAG
    embed_model: str = "gemini-embedding-2"
    embed_dim: int = 768
    rag_min_sim: float = 0.70  # calibrated on the golden set (make eval-rag)

    # Speech, push
    sarvam_api_key: SecretStr | None = None
    vapid_public_key: str | None = None
    vapid_private_key: SecretStr | None = None
    vapid_subject: str = "mailto:"
    expo_access_token: SecretStr | None = None

    # Data
    data_mode: Literal["online", "snapshot"] = "online"
    snapshot_date: str | None = None
    copernicusmarine_service_username: str | None = None
    copernicusmarine_service_password: SecretStr | None = None
    gfw_api_token: SecretStr | None = None

    # Graph, cache
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: SecretStr | None = None
    neo4j_database: str = "neo4j"
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    cache_disabled: bool = False

    # Wiring, telemetry
    mcp_url: str = "http://127.0.0.1:8001/mcp"
    agent_url: str = "http://127.0.0.1:8123"
    web_origin: str = "http://localhost:8081"
    otel_exporter_otlp_endpoint: str = "http://127.0.0.1:4317"

    # Agent improvement loop — test traffic only, never Tier 1
    traceroot_enabled: bool = False
    traceroot_api_key: SecretStr | None = None
    traceroot_host_url: str = "https://app.traceroot.ai"
    traceroot_environment: str = "local-eval"
    traceroot_user_salt: SecretStr | None = None

    # Tier 1 only
    frontdoor_id: str | None = None
    applicationinsights_connection_string: SecretStr | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
