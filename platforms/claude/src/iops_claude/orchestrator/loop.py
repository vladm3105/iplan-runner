"""The run loop: drive a validated intake manifest into a gated ledger.

Follows framework/execution/RUN_MODEL.md exactly so independent engines produce
byte-identical ledgers under injected clock + ids.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..executor.base import ExecutionContext, Executor
from ..gates.runner import run_gate
from ..ledger.store import append_event
from ..validation import status_of, validate_intake
from ..vcs.git import commit_all as git_commit_all
from ..vcs.git import has_changes as git_has_changes
from .leases import can_acquire
from .saga import already_committed, execute_with_retry
from .state import add_history, set_status, task
from .topo import topo_order

_AGENT_ID = "claude"


@dataclass
class RunResult:
    ledger: dict[str, Any]
    gate_result: dict[str, Any]


def default_gate() -> dict[str, Any]:
    return {
        "metadata": {"document_type": "iplan-verification-gate"},
        "gate_control": {"gate_id": "GATE-DEFAULT"},
        "gate_rules": [
            {"id": "GATE-LEDGER-001", "rule_ids": ["LEDGER.EVIDENCE_REQUIRED"]},
            {"id": "GATE-LEDGER-002", "rule_ids": ["LEDGER.ACCEPTANCE_WEAK"]},
            {"id": "GATE-LEDGER-003", "rule_ids": ["LEDGER.BLOCKED_WITHOUT_OWNER"]},
            {
                "id": "GATE-LEDGER-004",
                "rule_ids": [
                    "ISOLATION.SCOPE_MISSING",
                    "ISOLATION.PATH_OUTSIDE_ROOTS",
                    "ISOLATION.EVENT_SCOPE_MISMATCH",
                ],
            },
            {"id": "GATE-LEDGER-005", "rule_ids": ["HASHCHAIN.BROKEN"]},
            {"id": "GATE-LEDGER-006", "rule_ids": ["LEDGER.NOT_COMMITTED"]},
        ],
    }


def land(
    ledger: dict[str, Any],
    workspace: str,
    *,
    branch: str,
    message: str,
    clock: Callable[[], str],
    gate: dict[str, Any] | None = None,
) -> RunResult:
    """Commit a green run's workspace changes; no-op on a clean tree."""
    if git_has_changes(workspace):
        sha = git_commit_all(workspace, branch, message)
        at = clock()
        scope = ledger["isolation_scope"]
        touched = sorted(
            {
                p
                for e in ledger["execution_log"]
                if e["event_type"] == "file_edited"
                for p in e.get("touched_paths", [])
            }
        )
        vcs = ledger.setdefault("vcs", {})
        vcs["branch"] = branch
        vcs.setdefault("commits", []).append(
            {"sha": sha, "message": message, "at": at, "touched_paths": touched}
        )
        append_event(ledger, _event(scope, "commit", "LANDING", at, touched))
        ledger["ledger_control"]["requires_landing"] = True
    gate_result = run_gate(ledger, gate or default_gate())
    return RunResult(ledger=ledger, gate_result=gate_result)


def _init_ledger(manifest: dict[str, Any]) -> dict[str, Any]:
    control = manifest["intake_control"]
    graph = manifest["task_graph"]
    return {
        "metadata": {
            "schema_version": "1.0",
            "document_type": "iplan-ledger",
            "framework": "iops",
        },
        "ledger_control": {
            "ledger_id": "LEDGER-" + str(control["source_iplan"]),
            "source_iplan": control["source_iplan"],
            "source_iplan_version": control["source_iplan_version"],
            "source_iplan_checksum": control["source_iplan_checksum"],
            "status": "in_progress",
        },
        "isolation_scope": dict(manifest["isolation_scope"]),
        "task_ledger": [
            {
                "task_id": t["task_id"],
                "title": t.get("title"),
                "status": "pending",
                "evidence_refs": [],
                "acceptance": {
                    "criteria": (t.get("acceptance") or {}).get("criteria", []),
                    "result": "none",
                },
                "blocked_reason": None,
                "decision_owner": None,
            }
            for t in graph
        ],
        "agent_leases": [],
        "execution_evidence": [],
        "blockers": [],
        "reconciliation": {"allowed": False, "pending_tasks": len(graph), "open_blockers": 0},
        "saga_journal": [],
        "execution_history": [],
        "execution_log": [],
        "audit_snapshots": [],
    }


def _event(
    scope: dict[str, Any], event_type: str, task_id: str, at: str, paths: list[str]
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "subject_id": task_id,
        "at": at,
        "touched_paths": paths,
        "client_id": scope.get("client_id"),
        "project_id": scope.get("project_id"),
    }


def _escalate(
    ledger: dict[str, Any],
    task_id: str,
    reason: str,
    ids: Callable[[str], str],
    blocked_at: str,
) -> None:
    scope = ledger["isolation_scope"]
    ledger["blockers"].append(
        {
            "blocker_id": ids("B"),
            "task_id": task_id,
            "description": reason,
            "decision_owner": "operator",
        }
    )
    entry = task(ledger, task_id)
    entry["blocked_reason"] = reason
    entry["decision_owner"] = "operator"
    set_status(ledger, task_id, "blocked")
    add_history(ledger, task_id, "in_progress", "blocked", blocked_at)
    append_event(ledger, _event(scope, "task_blocked", task_id, blocked_at, []))


def _run_task(
    ledger: dict[str, Any],
    task_node: dict[str, Any],
    executor: Executor,
    clock: Callable[[], str],
    ids: Callable[[str], str],
    sleep: Callable[[float], None],
    max_retries: int,
    backoff_base: float,
) -> None:
    task_id = str(task_node["task_id"])
    scope = ledger["isolation_scope"]

    if already_committed(ledger, f"{task_id}-execute"):
        return  # idempotency: enables resume (Phase 9)

    acquired_at = clock()
    if not can_acquire(ledger["agent_leases"], task_id, acquired_at):
        _escalate(ledger, task_id, "lease conflict", ids, acquired_at)
        return
    lease = {
        "lease_id": ids("L"),
        "task_id": task_id,
        "agent_id": _AGENT_ID,
        "acquired_at": acquired_at,
        "expires_at": None,
        "released_at": None,
    }
    ledger["agent_leases"].append(lease)

    txn = {
        "txn_id": ids("TX"),
        "task_id": task_id,
        "action": "execute",
        "compensation": "revert",
        "idempotency_key": f"{task_id}-execute",
        "status": "pending",
        "timeout_s": 600,
    }
    ledger["saga_journal"].append(txn)

    started_at = clock()
    set_status(ledger, task_id, "in_progress")
    add_history(ledger, task_id, "pending", "in_progress", started_at)
    append_event(ledger, _event(scope, "task_started", task_id, started_at, []))

    ctx = ExecutionContext(task=task_node, isolation_scope=scope, clock=clock, ids=ids)
    result, attempts = execute_with_retry(
        executor, task_node, ctx, sleep=sleep, max_retries=max_retries, backoff_base=backoff_base
    )
    txn["attempts"] = attempts

    if result.outcome == "success":
        for path in result.touched_paths:
            append_event(ledger, _event(scope, "file_edited", task_id, clock(), [path]))
        if result.evidence is not None:
            evidence_id = ids("EV")
            ledger["execution_evidence"].append(
                {"evidence_id": evidence_id, "task_id": task_id, **result.evidence}
            )
            task(ledger, task_id)["evidence_refs"].append(evidence_id)
            task(ledger, task_id)["acceptance"]["result"] = "pass"
        completed_at = clock()
        set_status(ledger, task_id, "completed")
        add_history(ledger, task_id, "in_progress", "completed", completed_at)
        append_event(ledger, _event(scope, "task_completed", task_id, completed_at, []))
        txn["status"] = "committed"
    else:
        if result.touched_paths:
            executor.compensate(result.touched_paths)
            append_event(
                ledger, _event(scope, "compensation", task_id, clock(), result.touched_paths)
            )
            txn["status"] = "compensated"
        _escalate(ledger, task_id, result.reason or "execution failed", ids, clock())

    lease["released_at"] = clock()


def _block_unmet_deps(
    ledger: dict[str, Any],
    task_node: dict[str, Any],
    clock: Callable[[], str],
    ids: Callable[[str], str],
) -> None:
    """Block a task whose dependencies did not complete (no execution)."""
    task_id = str(task_node["task_id"])
    scope = ledger["isolation_scope"]
    reason = "dependency not satisfied"
    ledger["blockers"].append(
        {
            "blocker_id": ids("B"),
            "task_id": task_id,
            "description": reason,
            "decision_owner": "operator",
        }
    )
    at = clock()
    entry = task(ledger, task_id)
    entry["blocked_reason"] = reason
    entry["decision_owner"] = "operator"
    set_status(ledger, task_id, "blocked")
    add_history(ledger, task_id, "pending", "blocked", at)
    append_event(ledger, _event(scope, "task_blocked", task_id, at, []))


def _reconcile(ledger: dict[str, Any]) -> None:
    tasks = ledger["task_ledger"]
    pending = sum(1 for t in tasks if t["status"] in ("pending", "in_progress"))
    open_blockers = len(ledger["blockers"])
    allowed = pending == 0 and open_blockers == 0
    ledger["reconciliation"] = {
        "allowed": allowed,
        "pending_tasks": pending,
        "open_blockers": open_blockers,
    }
    if allowed:
        ledger["ledger_control"]["status"] = "completed"
    elif open_blockers:
        ledger["ledger_control"]["status"] = "blocked"


def run(
    manifest: dict[str, Any],
    executor: Executor,
    *,
    clock: Callable[[], str],
    ids: Callable[[str], str],
    sleep: Callable[[float], None],
    max_retries: int = 0,
    backoff_base: float = 0.0,
    gate: dict[str, Any] | None = None,
) -> RunResult:
    if status_of(validate_intake(manifest)) == "fail":
        raise ValueError("intake manifest failed validation")
    ledger = _init_ledger(manifest)
    by_id = {str(t["task_id"]): t for t in manifest["task_graph"]}
    completed: set[str] = set()
    for task_id in topo_order(manifest["task_graph"]):
        node = by_id[task_id]
        deps = [str(d) for d in node.get("depends_on", [])]
        if all(d in completed for d in deps):
            _run_task(ledger, node, executor, clock, ids, sleep, max_retries, backoff_base)
            if task(ledger, task_id)["status"] == "completed":
                completed.add(task_id)
        else:
            _block_unmet_deps(ledger, node, clock, ids)
    _reconcile(ledger)
    gate_result = run_gate(ledger, gate or default_gate())
    return RunResult(ledger=ledger, gate_result=gate_result)
