"""Build an `iplan-handover-receipt` from a completed ledger + gate verdict.

Deterministic: `created_at` comes from an injected clock and `receipt_id` is
derived from the ledger reference (no ambient ids/time).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_handover_receipt(
    ledger: dict[str, Any],
    gate_result: dict[str, Any],
    audit_report: dict[str, Any] | None = None,
    *,
    clock: Callable[[], str],
) -> dict[str, Any]:
    control = ledger.get("ledger_control", {})
    ledger_ref = control.get("ledger_id")
    tasks = ledger.get("task_ledger", [])
    has_open = any(t.get("status") in ("pending", "in_progress") for t in tasks)
    reconciled = bool(ledger.get("reconciliation", {}).get("allowed"))
    gate_passed = gate_result.get("status") == "passed"
    status = "completed" if (gate_passed and reconciled and not has_open) else "aborted"

    commits = ledger.get("vcs", {}).get("commits", [])
    commit = {"sha": commits[-1]["sha"], "branch": ledger.get("vcs", {}).get("branch")} if commits else None

    return {
        "metadata": {
            "schema_version": "1.0",
            "document_type": "iplan-handover-receipt",
            "framework": "iops",
        },
        "handover_control": {
            "receipt_id": f"RECEIPT-{ledger_ref}",
            "source_iplan": control.get("source_iplan"),
            "source_iplan_version": control.get("source_iplan_version"),
            "ledger_ref": ledger_ref,
            "gate_status": "passed" if gate_passed else "failed",
            "audit_report_ref": (audit_report or {}).get("audit_control", {}).get("report_id"),
            "commit": commit,
            "created_at": clock(),
        },
        "result": {"status": status, "reconciled": reconciled},
    }
