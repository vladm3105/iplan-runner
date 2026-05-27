"""Operator blocker resolution (see framework/execution/CONTROL_MODEL.md)."""

from __future__ import annotations

from typing import Any

from ..ledger.store import append_event
from ..security.authz import authorize


def resolve_blocker(
    ledger: dict[str, Any],
    blocker_id: str,
    decision: str,
    actor: dict[str, Any],
    *,
    at: str,
) -> dict[str, Any]:
    action = "override" if decision == "override" else "approve"
    verdict = authorize(actor, action)
    if not verdict["allowed"]:
        raise PermissionError(f"authz denied {decision}: {verdict['reason']}")

    blocker = next((b for b in ledger.get("blockers", []) if b.get("blocker_id") == blocker_id), None)
    task_id = blocker.get("task_id") if blocker else None

    ledger.setdefault("resolutions", []).append(
        {"blocker_id": blocker_id, "decision": decision, "actor": actor.get("id"), "at": at}
    )

    if decision == "override" and blocker is not None:
        ledger["blockers"] = [b for b in ledger["blockers"] if b.get("blocker_id") != blocker_id]
        for entry in ledger.get("task_ledger", []):
            if entry["task_id"] == task_id:
                entry["status"] = "pending"
                entry["blocked_reason"] = None

    scope = ledger.get("isolation_scope", {})
    append_event(
        ledger,
        {
            "event_type": "resolution",
            "subject_id": task_id,
            "at": at,
            "touched_paths": [],
            "client_id": scope.get("client_id"),
            "project_id": scope.get("project_id"),
        },
    )
    return ledger
