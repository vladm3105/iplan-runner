"""Durable relay state next to the ledger store (D-4b).

Extends the ``ledger/index.py`` dot-prefixed control-file pattern with three
sidecars per run: the **settled cursor** (the set of delivered/dead-lettered
projected ``idempotency_key``s — keyed on projected-event identity, NOT the raw
log ``sequence``, since projection skips kinds and fans ``task_completed`` out to
two events), a durable **dead-letter** sink, and the persisted **iplanic
identity** block the worker projects with. All writes are atomic (tmp + replace).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..ledger.events import _IDENTITY_FIELDS


def _path(store_dir: str | Path, ledger_id: str, suffix: str) -> Path:
    return Path(store_dir) / f".{ledger_id}.{suffix}"


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True))
    os.replace(tmp, path)


# --- settled cursor: the set of settled (delivered or dead-lettered) keys ---


def load_settled(store_dir: str | Path, ledger_id: str) -> set[str]:
    path = _path(store_dir, ledger_id, "relay-cursor")
    if not path.exists():
        return set()
    data: Any = json.loads(path.read_text())
    return set(data) if isinstance(data, list) else set()


def mark_settled(store_dir: str | Path, ledger_id: str, key: str) -> None:
    settled = load_settled(store_dir, ledger_id)
    settled.add(key)
    _atomic_write_json(_path(store_dir, ledger_id, "relay-cursor"), sorted(settled))


# --- dead-letter sink ---


def load_dead_letter(store_dir: str | Path, ledger_id: str) -> list[dict[str, Any]]:
    path = _path(store_dir, ledger_id, "relay-deadletter")
    if not path.exists():
        return []
    data: Any = json.loads(path.read_text())
    return data if isinstance(data, list) else []


def dead_letter(store_dir: str | Path, ledger_id: str, entry: dict[str, Any]) -> None:
    entries = load_dead_letter(store_dir, ledger_id)
    entries.append(entry)
    _atomic_write_json(_path(store_dir, ledger_id, "relay-deadletter"), entries)


# --- persisted iplanic identity (sidecar; the worker re-projects with it) ---


def save_identity(store_dir: str | Path, ledger_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Persist the payload's 8 identity fields so a later ``sync`` can project."""
    identity = {k: payload.get(k) for k in _IDENTITY_FIELDS}
    _atomic_write_json(_path(store_dir, ledger_id, "identity"), identity)
    return identity


def load_identity(store_dir: str | Path, ledger_id: str) -> dict[str, Any] | None:
    path = _path(store_dir, ledger_id, "identity")
    if not path.exists():
        return None
    data: Any = json.loads(path.read_text())
    return data if isinstance(data, dict) else None
