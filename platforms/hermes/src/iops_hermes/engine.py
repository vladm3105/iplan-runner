"""Hermes engine adapter.

Hermes exposes the execution contract as MCP-server-style tools and dispatches
execution via an API executor. It is fully self-contained: it imports only this
package and the framework spec, never another engine (strict isolation, D-0011).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import Config
from .gates.runner import run_gate
from .handover.receipt import build_handover_receipt
from .intake.reader import ingest_iplan
from .ledger.store import append_event
from .monitoring.otel import get_provider
from .monitoring.provider import MonitoringProvider, NoOpProvider
from .validation import (
    Finding,
    status_of,
    validate_audit,
    validate_chain,
    validate_handover,
    validate_intake,
    validate_ledger,
    validate_monitoring,
)

_DISPATCH: dict[str, Callable[[dict[str, Any]], list[Finding]]] = {
    "iplan-ledger": validate_ledger,
    "iplan-chain-ledger": validate_chain,
    "iplan-audit-report": validate_audit,
    "iplan-monitoring-manifest": validate_monitoring,
    "iplan-intake": validate_intake,
    "iplan-handover-receipt": validate_handover,
}

_SERVICE_NAME = "iops-hermes"


def _default_clock() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class HermesEngine:
    def __init__(self) -> None:
        self._provider: MonitoringProvider = NoOpProvider()
        self._config = Config()
        self._clock: Callable[[], str] = _default_clock

    def engine_id(self) -> str:
        return "hermes"

    def capabilities(self) -> dict[str, Any]:
        return {
            "validate": True,
            "gate": True,
            "audit": True,
            "monitor": True,
            "intake": True,
            "handover": True,
            "executor": "api",
        }

    def ingest_iplan(self, path: str | Path) -> dict[str, Any]:
        return ingest_iplan(path, self._config)

    def build_handover(
        self,
        ledger: dict[str, Any],
        gate_result: dict[str, Any],
        audit_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_handover_receipt(
            ledger, gate_result, audit_report, clock=self._clock
        )

    def validate(self, document: dict[str, Any]) -> dict[str, Any]:
        document_type = document.get("metadata", {}).get("document_type")
        validator = _DISPATCH.get(document_type)
        if validator is None:
            raise ValueError(f"unknown document_type: {document_type!r}")
        findings = validator(document)
        return {
            "status": status_of(findings),
            "findings": [
                {"rule_id": f.rule_id, "severity": f.severity, "message": f.message}
                for f in findings
            ],
        }

    def run_gate(self, ledger: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
        return run_gate(ledger, gate)

    def record_transaction(
        self, ledger: dict[str, Any], txn: dict[str, Any]
    ) -> dict[str, Any]:
        ledger.setdefault("saga_journal", []).append(txn)
        event = {
            "event_type": txn.get("action", "transaction"),
            "subject_id": txn.get("task_id"),
            "at": txn.get("at", ""),
            "touched_paths": txn.get("touched_paths", []),
            "client_id": ledger.get("isolation_scope", {}).get("client_id"),
            "project_id": ledger.get("isolation_scope", {}).get("project_id"),
        }
        append_event(ledger, event)
        return ledger

    def emit_execution_log(self, event: dict[str, Any]) -> None:
        self._provider.log("iplan.execution.event", "INFO", str(event))

    def instrument(self, manifest: dict[str, Any]) -> None:
        self._provider = get_provider(_SERVICE_NAME)

    # --- MCP-server-style tool surface ---------------------------------------

    def iops_validate_ledger(self, document: dict[str, Any]) -> dict[str, Any]:
        return self.validate(document)

    def iops_run_gate(
        self, ledger: dict[str, Any], gate: dict[str, Any]
    ) -> dict[str, Any]:
        return self.run_gate(ledger, gate)

    def iops_audit_report(self, document: dict[str, Any]) -> dict[str, Any]:
        return self.validate(document)

    def iops_monitor_check(self, document: dict[str, Any]) -> dict[str, Any]:
        return self.validate(document)

    def run_executor(self, prompt: str) -> dict[str, Any]:
        """API-executor dispatch stub, wrapped with execution-log emission."""
        self.emit_execution_log({"event_type": "executor_dispatch", "prompt": prompt})
        return {"engine": self.engine_id(), "dispatched": True, "prompt": prompt}
