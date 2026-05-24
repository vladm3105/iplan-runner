"""Execution-ledger validation (category IPLAN-007)."""
from __future__ import annotations

from typing import Any

from ..ledger.isolation import event_in_scope, in_scope
from ..ledger.store import verify_chain
from ._base import Finding, finding


def _leases_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        str(a.get("acquired_at")) < str(b.get("expires_at"))
        and str(b.get("acquired_at")) < str(a.get("expires_at"))
    )


def validate_ledger(document: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    control = document.get("ledger_control", {})
    if not (
        control.get("source_iplan")
        and control.get("source_iplan_version")
        and control.get("source_iplan_checksum")
    ):
        findings.append(
            finding(
                "LEDGER.SOURCE_VERSION_MISSING",
                "ledger_control is missing source IPLAN id/version/checksum",
            )
        )

    scope = document.get("isolation_scope", {})
    scope_ok = bool(
        scope.get("client_id")
        and scope.get("project_id")
        and scope.get("allowed_roots")
    )
    if not scope_ok:
        findings.append(
            finding(
                "ISOLATION.SCOPE_MISSING",
                "isolation_scope is missing client_id/project_id/allowed_roots",
            )
        )

    evidence = document.get("execution_evidence", [])
    for task in document.get("task_ledger", []):
        if task.get("status") == "completed":
            has_evidence = bool(task.get("evidence_refs")) or any(
                ev.get("task_id") == task.get("task_id") for ev in evidence
            )
            if not has_evidence:
                findings.append(
                    finding(
                        "LEDGER.EVIDENCE_REQUIRED",
                        f"completed task {task.get('task_id')} has no evidence",
                    )
                )
            if (task.get("acceptance") or {}).get("result") != "pass":
                findings.append(
                    finding(
                        "LEDGER.ACCEPTANCE_WEAK",
                        f"completed task {task.get('task_id')} acceptance is not pass",
                    )
                )
        if task.get("status") == "blocked" and not task.get("decision_owner"):
            findings.append(
                finding(
                    "LEDGER.BLOCKED_WITHOUT_OWNER",
                    f"blocked task {task.get('task_id')} has no decision_owner",
                )
            )

    for blocker in document.get("blockers", []):
        if not blocker.get("decision_owner"):
            findings.append(
                finding(
                    "LEDGER.BLOCKED_WITHOUT_OWNER",
                    f"blocker {blocker.get('blocker_id')} has no decision_owner",
                )
            )

    leases_by_task: dict[str, list[dict[str, Any]]] = {}
    for lease in document.get("agent_leases", []):
        if lease.get("released_at") is None:
            leases_by_task.setdefault(str(lease.get("task_id")), []).append(lease)
    for task_id, leases in leases_by_task.items():
        overlap = any(
            _leases_overlap(leases[i], leases[j])
            for i in range(len(leases))
            for j in range(i + 1, len(leases))
        )
        if overlap:
            findings.append(
                finding(
                    "LEDGER.LEASE_OVERLAP",
                    f"task {task_id} has overlapping unreleased leases",
                )
            )

    reconciliation = document.get("reconciliation", {})
    if reconciliation.get("allowed") and (
        int(reconciliation.get("pending_tasks", 0) or 0) > 0
        or int(reconciliation.get("open_blockers", 0) or 0) > 0
    ):
        findings.append(
            finding(
                "LEDGER.RECONCILE_INCONSISTENT",
                "reconciliation allowed while tasks/blockers remain",
            )
        )

    if scope_ok:
        roots = scope["allowed_roots"]
        client_id = scope["client_id"]
        project_id = scope["project_id"]
        path_violation = False
        scope_mismatch = False
        for event in document.get("execution_log", []):
            for path in event.get("touched_paths", []):
                if not in_scope(str(path), roots):
                    path_violation = True
            if not event_in_scope(event, client_id, project_id):
                scope_mismatch = True
        if path_violation:
            findings.append(
                finding(
                    "ISOLATION.PATH_OUTSIDE_ROOTS",
                    "an event touched a path outside allowed_roots",
                )
            )
        if scope_mismatch:
            findings.append(
                finding(
                    "ISOLATION.EVENT_SCOPE_MISMATCH",
                    "an event client_id/project_id differs from the ledger scope",
                )
            )

    if not verify_chain(document.get("execution_log", [])):
        findings.append(
            finding("HASHCHAIN.BROKEN", "execution_log hash chain is inconsistent")
        )

    if control.get("requires_landing") and not document.get("vcs", {}).get("commits"):
        findings.append(
            finding("LEDGER.NOT_COMMITTED", "requires_landing but no vcs commit recorded")
        )

    return findings
