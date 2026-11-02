from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ty_common.models import ToolResult


def test_tool_result_roundtrip() -> None:
    r = ToolResult(
        data={"wave_m": 1.2},
        source="open-meteo-marine",
        source_url="https://marine-api.open-meteo.com/v1/marine",
        fetched_at=datetime(2026, 11, 2, 0, 0, tzinfo=UTC),
        confidence="high",
    )
    assert r.cache == "miss"
    assert r.version() == "open-meteo-marine@2026-11-02T00:00:00+00:00"
    assert ToolResult.model_validate_json(r.model_dump_json()) == r


def test_naive_time_rejected() -> None:
    with pytest.raises(ValidationError):
        ToolResult(
            data={},
            source="x",
            source_url="https://x",
            fetched_at=datetime(2026, 11, 2),
            confidence="low",
        )
