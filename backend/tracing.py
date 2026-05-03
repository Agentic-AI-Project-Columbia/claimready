"""Optional OpenTelemetry tracing for the agent pipeline.

Activates when OTEL_EXPORTER_OTLP_ENDPOINT is set (e.g., to Cloud Trace
via the opentelemetry-exporter-gcp-trace package, or any OTLP endpoint).

Usage in main.py:
    from tracing import get_tracer
    tracer = get_tracer()
    with tracer.start_as_current_span("pipeline.run", attributes={"case_id": case_id}):
        ...
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("complaintgen.tracing")

_ENABLED = bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))


def setup_tracing() -> None:
    """Initialize OpenTelemetry SDK if an exporter endpoint is configured."""
    if not _ENABLED:
        log.info("OpenTelemetry tracing disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider()
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter()
        except ImportError:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter()

        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        log.info("OpenTelemetry tracing initialized")
    except ImportError:
        log.warning("OpenTelemetry packages not installed; tracing disabled")


def get_tracer():
    """Return a tracer instance (no-op if tracing is disabled)."""
    if not _ENABLED:
        from contextlib import contextmanager

        class _NoOpSpan:
            def set_attribute(self, key, value): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass

        class _NoOpTracer:
            @contextmanager
            def start_as_current_span(self, name, **kwargs):
                yield _NoOpSpan()

        return _NoOpTracer()

    from opentelemetry import trace
    return trace.get_tracer("complaintgen")
