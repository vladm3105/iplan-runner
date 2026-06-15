"""Durable, atomic, lock-guarded ledger persistence."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .store import verify_chain


def ledger_path(store_dir: str | Path, ledger_id: str) -> Path:
    return Path(store_dir) / f"{ledger_id}.yaml"


def save(ledger: dict[str, Any], store_dir: str | Path) -> Path:
    """Atomically write the ledger under an advisory lock."""
    ledger_id = ledger["ledger_control"]["ledger_id"]
    store = Path(store_dir)
    store.mkdir(parents=True, exist_ok=True)
    path = ledger_path(store, ledger_id)
    lock_path = store / f".{ledger_id}.lock"
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            tmp = path.with_suffix(".yaml.tmp")
            with open(tmp, "w") as handle:
                yaml.safe_dump(ledger, handle, sort_keys=False)
            os.replace(tmp, path)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    return path


def load(path: str | Path) -> dict[str, Any]:
    data: Any = yaml.safe_load(Path(path).read_text())
    ledger = data if isinstance(data, dict) else {}
    if not verify_chain(ledger.get("execution_log", [])):
        raise ValueError(f"hash chain verification failed for {path}")
    return ledger
