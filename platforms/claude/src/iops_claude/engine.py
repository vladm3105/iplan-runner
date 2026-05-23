"""Claude engine adapter.

The Claude engine integrates with Claude Code: it implements the
AGENT_UPDATE_PROTOCOL (session start -> lease -> edit recording -> evidence ->
reconciliation) and records ledger transactions from observed local edits / hook
callbacks. It is fully self-contained: it imports only this package and the
framework spec, never another engine (strict isolation, D-0011).

Slice 1 exercises these methods programmatically; live Claude Code hook wiring is
a follow-up (see HOOK_INTEGRATION_POINTS in the framework spec).
"""
from __future__ import annotations

from typing import Any, Callable

from .gates.runner import run_gate
from .ledger.store import append_event
from .monitoring.otel import get_provider
from .monitoring.provider import MonitoringProvider, NoOpProvider
from .validation import (
    Finding,
    status_of,
    validate_audit,
    validate_chain,
    validate_ledger,
    validate_monitoring,
)

_DISPATCH: dict[str, Callable[[dict[str, Any]], list[Finding]]] = {
    "iplan-ledger": validate_ledger,
    "iplan-chain-ledger": validate_chain,
    "iplan-audit-report": validate_audit,
    "iplan-monitoring-manifest": validate_monitoring,
}

_SERVICE_NAME = "iops-claude"


class ClaudeEngine:
    def __init__(self) -> None:
        self._provider: MonitoringProvider = NoOpProvider()

    def engine_id(self) -> str:
        return "claude"

    def capabilities(self) -> dict[str, Any]:
        return {
            "validate": True,
            "gate": True,
            "audit": True,
            "monitor": True,
            "executor": "hooks",
        }

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

    # --- AGENT_UPDATE_PROTOCOL ------------------------------------------------

    def start_session(self, ledger: dict[str, Any]) -> dict[str, Any]:
        ledger.setdefault("execution_log", [])
        ledger.setdefault("agent_leases", [])
        return ledger

    def acquire_lease(
        self, ledger: dict[str, Any], lease: dict[str, Any]
    ) -> dict[str, Any]:
        ledger.setdefault("agent_leases", []).append(lease)
        return ledger

    def record_touched_file(
        self, ledger: dict[str, Any], task_id: str, path: str, at: str
    ) -> dict[str, Any]:
        scope = ledger.get("isolation_scope", {})
        append_event(
            ledger,
            {
                "event_type": "file_edited",
                "subject_id": task_id,
                "at": at,
                "touched_paths": [path],
                "client_id": scope.get("client_id"),
                "project_id": scope.get("project_id"),
            },
        )
        return ledger

    def record_evidence(
        self, ledger: dict[str, Any], evidence: dict[str, Any]
    ) -> dict[str, Any]:
        ledger.setdefault("execution_evidence", []).append(evidence)
        return ledger

    def reconcile(self, ledger: dict[str, Any]) -> dict[str, Any]:
        tasks = ledger.get("task_ledger", [])
        pending = sum(
            1 for t in tasks if t.get("status") in ("pending", "in_progress")
        )
        open_blockers = len(ledger.get("blockers", []))
        ledger["reconciliation"] = {
            "allowed": pending == 0 and open_blockers == 0,
            "pending_tasks": pending,
            "open_blockers": open_blockers,
        }
        return ledger
