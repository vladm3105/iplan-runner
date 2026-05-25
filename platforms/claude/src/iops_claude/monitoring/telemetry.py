"""Engine self-telemetry: emit the run's own signals (distinct from product SLOs)."""

from __future__ import annotations

from typing import Any

from .provider import MonitoringProvider


def emit_run_telemetry(provider: MonitoringProvider, ledger: dict[str, Any]) -> None:
    tasks = ledger.get("task_ledger", [])
    completed = sum(1 for t in tasks if t.get("status") == "completed")
    blocked = sum(1 for t in tasks if t.get("status") == "blocked")
    provider.record_metric("iplan.tasks.total", float(len(tasks)))
    provider.record_metric("iplan.tasks.completed", float(completed))
    provider.record_metric("iplan.tasks.blocked", float(blocked))
