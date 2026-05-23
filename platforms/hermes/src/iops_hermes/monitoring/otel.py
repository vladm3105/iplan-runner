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
    """Minimal OTel provider: emits spans. Metrics/logs are no-ops in slice 1."""

    def __init__(self, service_name: str) -> None:
        trace = importlib.import_module("opentelemetry.trace")
        self._tracer = trace.get_tracer(service_name)

    def start_span(self, name: str, attributes: dict[str, Any]) -> None:
        span = self._tracer.start_span(name, attributes=attributes)
        span.end()

    def record_metric(self, name: str, value: float) -> None:
        return None

    def log(self, name: str, severity: str, body: str) -> None:
        return None


def get_provider(service_name: str) -> MonitoringProvider:
    try:
        importlib.import_module("opentelemetry.trace")
    except ImportError:
        return NoOpProvider()
    try:
        return _OtelProvider(service_name)
    except Exception:
        return NoOpProvider()
