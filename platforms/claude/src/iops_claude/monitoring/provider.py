"""Monitoring provider interface + a no-op default (no OTel dependency)."""
from __future__ import annotations

from typing import Any, Protocol


class MonitoringProvider(Protocol):
    def start_span(self, name: str, attributes: dict[str, Any]) -> None: ...

    def record_metric(self, name: str, value: float) -> None: ...

    def log(self, name: str, severity: str, body: str) -> None: ...


class NoOpProvider:
    """Used when the optional ``[otel]`` extra is not installed."""

    def start_span(self, name: str, attributes: dict[str, Any]) -> None:
        return None

    def record_metric(self, name: str, value: float) -> None:
        return None

    def log(self, name: str, severity: str, body: str) -> None:
        return None
