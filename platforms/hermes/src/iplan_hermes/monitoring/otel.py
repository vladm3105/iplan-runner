"""OpenTelemetry-backed provider, behind the optional ``[otel]`` extra.

Imported lazily via importlib so the engine builds and tests run without the
OTel SDK installed. Absent it (or on any wiring error), the no-op provider is
returned so the contract and SLO evaluation still work offline.
"""

from __future__ import annotations

import importlib
from typing import Any

from .provider import MonitoringProvider, NoOpProvider


class _OtelProvider:
    """OTel provider: spans + metrics (counters) + logs (span events). Best-effort."""

    def __init__(self, service_name: str) -> None:
        trace = importlib.import_module("opentelemetry.trace")
        metrics = importlib.import_module("opentelemetry.metrics")
        self._tracer = trace.get_tracer(service_name)
        self._meter = metrics.get_meter(service_name)
        self._counters: dict[str, Any] = {}

    def start_span(self, name: str, attributes: dict[str, Any]) -> None:
        span = self._tracer.start_span(name, attributes=attributes)
        span.end()

    def record_metric(self, name: str, value: float) -> None:
        counter = self._counters.get(name)
        if counter is None:
            counter = self._meter.create_counter(name)
            self._counters[name] = counter
        counter.add(value)

    def log(self, name: str, severity: str, body: str) -> None:
        span = self._tracer.start_span(name)
        span.add_event(severity, {"body": body})
        span.end()


def get_provider(service_name: str) -> MonitoringProvider:
    try:
        importlib.import_module("opentelemetry.trace")
    except ImportError:
        return NoOpProvider()
    try:
        return _OtelProvider(service_name)
    except Exception:
        return NoOpProvider()
