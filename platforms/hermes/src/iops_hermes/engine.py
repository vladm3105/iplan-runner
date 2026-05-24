"""Hermes engine adapter.

Hermes exposes the execution contract as MCP-server-style tools and dispatches
execution via an API executor. It is fully self-contained: it imports only this
package and the framework spec, never another engine (strict isolation, D-0011).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .budget import Budget
from .config import Config
from .effectors.sandbox import classify_path
from .executor.api import ApiExecutor
from .executor.base import Executor
from .executor.mock import MockExecutor
from .executor.scripted import ScriptedExecutor
from .gates.runner import run_gate
from .model.client import ModelClient
from .handover.receipt import build_handover_receipt
from .intake.reader import ingest_iplan
from .ledger.store import append_event
from .monitoring.otel import get_provider
from .monitoring.provider import MonitoringProvider, NoOpProvider
from .orchestrator.loop import RunResult, default_gate
from .orchestrator.loop import land as _land
from .orchestrator.loop import run as _run
from .security.authz import authorize as _authorize
from .security.signing import sign_ledger as _sign_ledger
from .security.signing import verify_ledger as _verify_ledger
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
            "run": True,
            "persist": True,
            "effect": True,
            "evidence": True,
            "executor": "api",
        }

    def ingest_iplan(self, path: str | Path) -> dict[str, Any]:
        return ingest_iplan(path, self._config)

    def classify_path(self, path: str, allowed_roots: list[str]) -> dict[str, Any]:
        return classify_path(path, allowed_roots)

    def default_gate(self) -> dict[str, Any]:
        return default_gate()

    def mock_executor(self, outcomes: dict[str, Any] | None = None) -> Executor:
        return MockExecutor(outcomes)

    def scripted_executor(
        self, spec: dict[str, Any] | None = None, workspace: str | Path = "."
    ) -> Executor:
        return ScriptedExecutor(spec, workspace, self._config.secrets)

    def api_executor(
        self,
        client: ModelClient,
        workspace: str | Path = ".",
        budget: Budget | None = None,
    ) -> Executor:
        return ApiExecutor(client, workspace, budget, self._config.secrets)

    def default_executor(self) -> Executor:
        return MockExecutor()

    def run(
        self,
        manifest: dict[str, Any],
        executor: Executor,
        *,
        clock: Callable[[], str],
        ids: Callable[[str], str],
        sleep: Callable[[float], None] | None = None,
        max_retries: int | None = None,
    ) -> RunResult:
        return _run(
            manifest,
            executor,
            clock=clock,
            ids=ids,
            sleep=sleep if sleep is not None else time.sleep,
            max_retries=max_retries if max_retries is not None else self._config.max_retries,
            backoff_base=self._config.backoff_base,
            gate=self.default_gate(),
        )

    def authorize(self, actor: dict[str, Any], action: str) -> dict[str, Any]:
        return _authorize(actor, action)

    def sign_ledger(self, ledger: dict[str, Any], key: str | None = None) -> dict[str, Any]:
        return _sign_ledger(ledger, key if key is not None else (self._config.signing_key or ""))

    def verify_ledger(self, ledger: dict[str, Any], key: str | None = None) -> bool:
        return _verify_ledger(ledger, key if key is not None else (self._config.signing_key or ""))

    def land(
        self,
        ledger: dict[str, Any],
        workspace: str,
        *,
        branch: str,
        message: str = "iops landing",
        clock: Callable[[], str] | None = None,
        actor: dict[str, Any] | None = None,
    ) -> RunResult:
        if actor is not None:
            decision = _authorize(actor, "land")
            if not decision["allowed"]:
                raise PermissionError(f"authz denied land: {decision['reason']}")
        result = _land(
            ledger,
            workspace,
            branch=branch,
            message=message,
            clock=clock if clock is not None else _default_clock,
            gate=self.default_gate(),
        )
        if self._config.signing_key:
            _sign_ledger(result.ledger, self._config.signing_key)
        return result

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
