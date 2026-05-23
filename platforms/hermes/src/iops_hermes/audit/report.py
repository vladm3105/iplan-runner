"""Build a version-comparison audit report from two ledgers."""
from __future__ import annotations

from typing import Any


def _scope(ledger: dict[str, Any]) -> dict[str, Any]:
    control = ledger.get("ledger_control", {})
    return {
        "ledger_id": control.get("ledger_id"),
        "source_iplan": control.get("source_iplan"),
        "source_iplan_version": control.get("source_iplan_version"),
        "source_iplan_checksum": control.get("source_iplan_checksum"),
    }


def _task_ids(ledger: dict[str, Any]) -> set[str]:
    return {str(t.get("task_id")) for t in ledger.get("task_ledger", [])}


def build_audit_report(
    baseline: dict[str, Any], comparison: dict[str, Any]
) -> dict[str, Any]:
    base_tasks = _task_ids(baseline)
    comp_tasks = _task_ids(comparison)
    added = sorted(comp_tasks - base_tasks)
    removed = sorted(base_tasks - comp_tasks)

    return {
        "metadata": {
            "schema_version": "1.0",
            "document_type": "iplan-audit-report",
            "framework": "iops",
        },
        "audit_control": {"report_id": "AUDIT-GEN", "status": "draft"},
        "version_scope": {
            "baseline": _scope(baseline),
            "comparison": _scope(comparison),
        },
        "execution_summary": {
            "tasks_total": len(comp_tasks),
            "tasks_added": len(added),
            "tasks_removed": len(removed),
        },
        "change_report": {
            "added_tasks": added,
            "removed_tasks": removed,
            "status_changes": [],
        },
        "audit_findings": [],
        "recommendation": "investigate",
    }
