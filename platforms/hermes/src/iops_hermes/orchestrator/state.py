"""Task-state transitions over a ledger."""
from __future__ import annotations

from typing import Any


def task(ledger: dict[str, Any], task_id: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = ledger["task_ledger"]
    for entry in entries:
        if entry["task_id"] == task_id:
            return entry
    raise KeyError(task_id)


def set_status(ledger: dict[str, Any], task_id: str, new_status: str) -> None:
    task(ledger, task_id)["status"] = new_status


def add_history(
    ledger: dict[str, Any], task_id: str, from_status: str, to_status: str, at: str
) -> None:
    ledger["execution_history"].append(
        {
            "at": at,
            "task_id": task_id,
            "from_status": from_status,
            "to_status": to_status,
        }
    )
