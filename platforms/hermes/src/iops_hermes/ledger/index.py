"""Status/query surface over a ledger store directory."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .persistence import ledger_path, load


def list_runs(store_dir: str | Path) -> list[str]:
    store = Path(store_dir)
    if not store.is_dir():
        return []
    return sorted(p.stem for p in store.glob("*.yaml"))


def status(ledger_id: str, store_dir: str | Path) -> dict[str, Any]:
    ledger = load(ledger_path(store_dir, ledger_id))
    tasks = ledger.get("task_ledger", [])
    by_status: dict[str, int] = {}
    for entry in tasks:
        by_status[entry["status"]] = by_status.get(entry["status"], 0) + 1
    return {
        "ledger_id": ledger_id,
        "source_iplan": ledger.get("ledger_control", {}).get("source_iplan"),
        "tasks": by_status,
        "reconciliation": ledger.get("reconciliation", {}),
        "open_blockers": len(ledger.get("blockers", [])),
    }
