"""Status/query surface over a ledger store directory."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .persistence import ledger_path, load


def _control_path(store_dir: str | Path, ledger_id: str) -> Path:
    return Path(store_dir) / f".{ledger_id}.control"


def set_control(ledger_id: str, state: str, store_dir: str | Path) -> None:
    Path(store_dir).mkdir(parents=True, exist_ok=True)
    _control_path(store_dir, ledger_id).write_text(state)


def get_control(ledger_id: str, store_dir: str | Path) -> str:
    path = _control_path(store_dir, ledger_id)
    return path.read_text().strip() if path.exists() else "running"


def store_control(ledger_id: str, store_dir: str | Path) -> Callable[[], str]:
    """A control callable that reads the store flag (cross-process operator control)."""
    return lambda: get_control(ledger_id, store_dir)


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
