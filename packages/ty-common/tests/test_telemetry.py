from __future__ import annotations

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ty_common import telemetry
from ty_common.settings import get_settings


def test_scrub_patterns() -> None:
    s = telemetry.scrub(
        "mail gurjas@example.com phone +91 9876543210 at 9.28812, 79.31345 token eyJabc.def.ghi Bearer xyz"
    )
    assert "example.com" not in s and "9876543210" not in s and "79.31345" not in s
    assert "eyJabc" not in s and "xyz" not in s
    assert telemetry.scrub("waves 0.7 m at 05:30") == "waves 0.7 m at 05:30"  # ordinary figures survive


def test_exported_spans_are_scrubbed() -> None:
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(telemetry.scrubbing_exporter(memory)))
    tracer = provider.get_tracer("t")
    with tracer.start_as_current_span("answer") as span:
        span.set_attribute("input", "I am at 9.28812, 79.31345, call 9876543210")
        span.add_event("tool", {"args": "lat 9.28812, 79.31345"})
    (out,) = memory.get_finished_spans()
    assert "79.31345" not in str(out.attributes) and "9876543210" not in str(out.attributes)
    assert "79.31345" not in str(out.events[0].attributes)


def test_traceroot_refused_in_live(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "traceroot_enabled", True)
    monkeypatch.setattr(s, "env", "live")
    with pytest.raises(RuntimeError, match="SEC-14"):
        telemetry.init_tracing("ty-agent")
