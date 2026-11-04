"""One tracer per process (spec §10.1, §10.4).

- TRACEROOT_ENABLED=true → TraceRoot (test traffic only; refuses to start when ENV=live — SEC-14).
- APPLICATIONINSIGHTS_CONNECTION_STRING set → Azure Monitor (Tier 1).
- otherwise → OTLP to OTEL_EXPORTER_OTLP_ENDPOINT (grafana/otel-lgtm on the laptop).

A span processor scrubs tokens, phone numbers, e-mail addresses and coordinate pairs from every span attribute
before export.
"""

from __future__ import annotations

import hashlib
import logging
import re
from contextlib import AbstractContextManager, nullcontext
from typing import Any

from .settings import get_settings

log = logging.getLogger(__name__)

_SCRUB = [
    (re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"), "[token]"),  # JWT
    (re.compile(r"(?i)bearer\s+\S+"), "Bearer [token]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[phone]"),
    (re.compile(r"-?\d{1,2}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}"), "[coords]"),
]
_initialised = False


def scrub(text: str) -> str:
    for pat, repl in _SCRUB:
        text = pat.sub(repl, text)
    return text


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, (list, tuple)):
        return type(value)(scrub(v) if isinstance(v, str) else v for v in value)
    return value


def scrubbing_exporter(inner: Any) -> Any:
    """Wraps a SpanExporter: every span is exported as a copy with tokens, phones, e-mails and coordinate pairs
    removed from its attributes and event attributes. Never raises into the request path."""
    from opentelemetry.sdk.trace import Event, ReadableSpan
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

    class ScrubbingExporter(SpanExporter):
        def export(self, spans: Any) -> Any:
            try:
                clean = [
                    ReadableSpan(
                        name=sp.name,
                        context=sp.context,
                        parent=sp.parent,
                        resource=sp.resource,
                        attributes={k: _clean(v) for k, v in (sp.attributes or {}).items()},
                        events=[
                            Event(e.name, {k: _clean(v) for k, v in (e.attributes or {}).items()}, e.timestamp)
                            for e in sp.events
                        ],
                        links=sp.links,
                        kind=sp.kind,
                        status=sp.status,
                        start_time=sp.start_time,
                        end_time=sp.end_time,
                        instrumentation_scope=sp.instrumentation_scope,
                    )
                    for sp in spans
                ]
                return inner.export(clean)
            except Exception:  # telemetry must never break an answer
                log.warning("span export failed", exc_info=True)
                return SpanExportResult.FAILURE

        def shutdown(self) -> None:
            inner.shutdown()

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return bool(inner.force_flush(timeout_millis))

    return ScrubbingExporter()


def _setup_otlp(service: str) -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    exporter = OTLPSpanExporter(endpoint=get_settings().otel_exporter_otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(scrubbing_exporter(exporter)))
    trace.set_tracer_provider(provider)


def init_tracing(service: str) -> str:
    """Set exactly one tracer for this process. Returns which one."""
    global _initialised
    s = get_settings()
    if s.traceroot_enabled and s.env == "live":
        raise RuntimeError("TraceRoot is for test traffic only (SEC-14): unset TRACEROOT_ENABLED in live")
    if _initialised:
        return "already"
    _initialised = True
    try:
        if s.traceroot_enabled:
            import traceroot
            from traceroot import Integration

            traceroot.initialize(integrations=[Integration.LANGCHAIN, Integration.GOOGLE_GENAI])
            return "traceroot"
        if s.applicationinsights_connection_string is not None:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(connection_string=s.applicationinsights_connection_string.get_secret_value())
            return "azure"
        _setup_otlp(service)
        try:
            from openinference.instrumentation.langchain import LangChainInstrumentor

            LangChainInstrumentor().instrument()
        except ImportError:
            pass
        return "otlp"
    except ImportError as e:
        log.warning("tracing not initialised (%s)", e)
        return "none"


def pseudonym(user_sub: str | None) -> str | None:
    s = get_settings()
    if not user_sub:
        return None
    salt = s.traceroot_user_salt.get_secret_value() if s.traceroot_user_salt else "local"
    return hashlib.sha256(f"{salt}:{user_sub}".encode()).hexdigest()[:16]


def trace_context(
    *, thread_id: str, user_sub: str | None, lang: str, mode: str, versions: dict[str, str]
) -> AbstractContextManager[Any]:
    """Attributes on every agent run; a no-op outside improvement runs."""
    s = get_settings()
    if not s.traceroot_enabled:
        return nullcontext()
    from traceroot import using_attributes

    return using_attributes(  # type: ignore[no-any-return]
        user_id=pseudonym(user_sub),
        session_id=thread_id,
        tags=[f"lang:{lang}", f"mode:{mode}", s.traceroot_environment],
        metadata=versions,
    )


def record_guardrails(outcome: dict[str, Any]) -> None:
    """Validator results on the trace (TraceRoot) or the current OTel span."""
    s = get_settings()
    if s.traceroot_enabled:
        from traceroot import update_current_trace

        update_current_trace(
            metadata={f"guard.{k}": v for k, v in outcome.items()},
            tags=[f"guard:{k}" for k, v in outcome.items() if v],
        )
        return
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        for k, v in outcome.items():
            span.set_attribute(f"ty.guard.{k}", v if isinstance(v, (bool, int, float, str)) else str(v))
    except ImportError:
        pass
