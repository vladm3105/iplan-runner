"""Monitoring: provider interface (no-op default), optional OTel, SLO eval."""

from .provider import MonitoringProvider, NoOpProvider
from .otel import get_provider
from .slo import evaluate_slos

__all__ = ["MonitoringProvider", "NoOpProvider", "get_provider", "evaluate_slos"]
