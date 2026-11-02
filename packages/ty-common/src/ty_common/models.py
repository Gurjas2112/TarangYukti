"""The contract every data tool returns (prompt §7, spec §6.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolResult(BaseModel):
    """A grounded tool result. Every number the agent says must come from one of these."""

    model_config = ConfigDict(strict=True, extra="forbid")

    data: dict[str, object] | list[object]
    source: str
    source_url: str
    fetched_at: datetime  # stored UTC, shown IST
    valid_at: datetime | None = None  # when the value is true (bi-temporal ledger, spec §6.1.5.1)
    confidence: Literal["high", "medium", "low"]
    cache: Literal["miss", "hit", "stale", "snapshot"] = "miss"
    notes: list[str] = Field(default_factory=list)

    @field_validator("fetched_at", "valid_at")
    @classmethod
    def _must_be_aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC)")
        return v

    def version(self) -> str:
        """Input data version used in cache fingerprints: source + upstream issue time."""
        stamp = (self.valid_at or self.fetched_at).isoformat()
        return f"{self.source}@{stamp}"
