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

import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .budget import Budget
from .config import Config
from .effectors.sandbox import classify_path
from .executor.base import Executor
from .executor.hostruntime import HostRuntimeExecutor
from .executor.mock import MockExecutor
from .executor.scripted import ScriptedExecutor
from .gates.runner import run_gate
from .handover.receipt import build_handover_receipt
from .intake.reader import ingest_iplan
from .ledger.index import set_control
from .ledger.store import append_event
from .monitoring.alerts import build_issue as _build_issue
from .monitoring.alerts import evaluate_alerts as _evaluate_alerts
from .monitoring.otel import get_provider
from .monitoring.provider import MonitoringProvider, NoOpProvider
from .orchestrator.chain import ChainResult
from .orchestrator.chain import run_chain as _run_chain
from .orchestrator.control import resolve_blocker as _resolve_blocker
from .orchestrator.loop import RunResult, default_gate
from .orchestrator.loop import land as _land
from .orchestrator.loop import resume as _resume
from .orchestrator.loop import run as _run
from .runtime.client import RuntimeClient
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

_SERVICE_NAME = "iops-claude"


def _default_clock() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ClaudeEngine:
    def __init__(self) -> None:
        self._provider: MonitoringProvider = NoOpProvider()
        self._config = Config()
        self._clock: Callable[[], str] = _default_clock

    def engine_id(self) -> str:
        return "claude"

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
            "executor": "hooks",
        }

    def ingest_iplan(self, path: str | Path) -> dict[str, Any]:
        return ingest_iplan(path, self._config)

    def classify_path(self, path: str, allowed_roots: list[str], forbidden_paths: Sequence[str] = ()) -> dict[str, Any]:
        return classify_path(path, allowed_roots, forbidden_paths)

    def default_gate(self) -> dict[str, Any]:
        return default_gate()

    def mock_executor(self, outcomes: dict[str, Any] | None = None) -> Executor:
        return MockExecutor(outcomes)

    def scripted_executor(self, spec: dict[str, Any] | None = None, workspace: str | Path = ".") -> Executor:
        return ScriptedExecutor(spec, workspace, self._config.secrets)

    def host_executor(
        self,
        client: RuntimeClient,
        workspace: str | Path = ".",
        budget: Budget | None = None,
    ) -> Executor:
        return HostRuntimeExecutor(client, workspace, budget)

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
        control: Callable[[], str] | None = None,
    ) -> RunResult:
        return _run(
            manifest,
            executor,
            clock=clock,
            ids=ids,
            sleep=sleep if sleep is not None else time.sleep,
            max_retries=max_retries if max_retries is not None else self._config.max_retries,
            backoff_base=self._config.backoff_base,
            control=control,
            gate=self.default_gate(),
        )

    def resume(
        self,
        manifest: dict[str, Any],
        ledger: dict[str, Any],
        executor: Executor,
        *,
        clock: Callable[[], str],
        ids: Callable[[str], str],
        sleep: Callable[[float], None] | None = None,
        max_retries: int | None = None,
        control: Callable[[], str] | None = None,
    ) -> RunResult:
        return _resume(
            manifest,
            ledger,
            executor,
            clock=clock,
            ids=ids,
            sleep=sleep if sleep is not None else time.sleep,
            max_retries=max_retries if max_retries is not None else self._config.max_retries,
            backoff_base=self._config.backoff_base,
            control=control,
            gate=self.default_gate(),
        )

    def resolve_blocker(
        self,
        ledger: dict[str, Any],
        blocker_id: str,
        decision: str,
        actor: dict[str, Any],
        *,
        clock: Callable[[], str] | None = None,
    ) -> dict[str, Any]:
        at = (clock if clock is not None else _default_clock)()
        return _resolve_blocker(ledger, blocker_id, decision, actor, at=at)

    def run_chain(
        self,
        chain: dict[str, Any],
        iplans: dict[str, dict[str, Any]],
        executor_for: Callable[[str], Executor],
        *,
        clock: Callable[[], str],
        ids: Callable[[str], str],
        sleep: Callable[[float], None] | None = None,
        control: Callable[[], str] | None = None,
    ) -> ChainResult:
        return _run_chain(
            chain,
            iplans,
            executor_for,
            clock=clock,
            ids=ids,
            sleep=sleep if sleep is not None else time.sleep,
            control=control,
            gate=self.default_gate(),
        )

    def pause(self, ledger_id: str, store_dir: str) -> None:
        set_control(ledger_id, "paused", store_dir)

    def abort(self, ledger_id: str, store_dir: str) -> None:
        set_control(ledger_id, "aborted", store_dir)

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
        return build_handover_receipt(ledger, gate_result, audit_report, clock=self._clock)

    def validate(self, document: dict[str, Any]) -> dict[str, Any]:
        document_type = document.get("metadata", {}).get("document_type")
        validator = _DISPATCH.get(document_type)
        if validator is None:
            raise ValueError(f"unknown document_type: {document_type!r}")
        findings = validator(document)
        return {
            "status": status_of(findings),
            "findings": [{"rule_id": f.rule_id, "severity": f.severity, "message": f.message} for f in findings],
        }

    def run_gate(self, ledger: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
        return run_gate(ledger, gate)

    def record_transaction(self, ledger: dict[str, Any], txn: dict[str, Any]) -> dict[str, Any]:
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

    def evaluate_alerts(self, manifest: dict[str, Any], samples: dict[str, float]) -> list[dict[str, Any]]:
        return _evaluate_alerts(manifest, samples)

    def build_issue(self, alert: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
        return _build_issue(alert, manifest)

    # --- AGENT_UPDATE_PROTOCOL ------------------------------------------------

    def start_session(self, ledger: dict[str, Any]) -> dict[str, Any]:
        ledger.setdefault("execution_log", [])
        ledger.setdefault("agent_leases", [])
        return ledger

    def acquire_lease(self, ledger: dict[str, Any], lease: dict[str, Any]) -> dict[str, Any]:
        ledger.setdefault("agent_leases", []).append(lease)
        return ledger

    def record_touched_file(self, ledger: dict[str, Any], task_id: str, path: str, at: str) -> dict[str, Any]:
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

    def record_evidence(self, ledger: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        ledger.setdefault("execution_evidence", []).append(evidence)
        return ledger

    def reconcile(self, ledger: dict[str, Any]) -> dict[str, Any]:
        tasks = ledger.get("task_ledger", [])
        pending = sum(1 for t in tasks if t.get("status") in ("pending", "in_progress"))
        open_blockers = len(ledger.get("blockers", []))
        ledger["reconciliation"] = {
            "allowed": pending == 0 and open_blockers == 0,
            "pending_tasks": pending,
            "open_blockers": open_blockers,
        }
        return ledger
