"""Durable relay operational state next to the ledger store (D-4c).

A per-store SQLite database (`<store>/relay.db`, stdlib `sqlite3`, WAL) holding the
relay's **operational** state — distinct from the signed ledger, which stays a
portable file (D-0021). It is an **outbox keyed on the projected `idempotency_key`**
(the key iplanic dedups on): one `delivery` row per settled event records
`delivered` or `dead_lettered`, so a dead-letter write **is** the cursor mark in a
single transaction (D-4b's two-write window is gone). The `identity` table persists
the iplanic identity the worker re-projects with.

The public interface is unchanged from the D-4b JSON-sidecar implementation, so
`relay/worker.py`, the CLI `sync`, and the gated integration suite are the
regression oracle.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..ledger.events import _IDENTITY_FIELDS

_DELIVERED = "delivered"
_DEAD_LETTERED = "dead_lettered"


def _db_path(store_dir: str | Path) -> Path:
    return Path(store_dir) / "relay.db"


def _connect(store_dir: str | Path) -> sqlite3.Connection:
    """Open `<store>/relay.db` (WAL + busy_timeout) and ensure the schema exists."""
    Path(store_dir).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_db_path(store_dir), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS delivery ("
        "ledger_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, status TEXT NOT NULL, "
        "reason TEXT, event_json TEXT, updated_at TEXT NOT NULL, "
        "PRIMARY KEY (ledger_id, idempotency_key))"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS identity (ledger_id TEXT PRIMARY KEY, identity_json TEXT NOT NULL)")
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat()


# --- settled cursor: the set of settled (delivered or dead-lettered) keys ---


def load_settled(store_dir: str | Path, ledger_id: str) -> set[str]:
    conn = _connect(store_dir)
    try:
        rows = conn.execute("SELECT idempotency_key FROM delivery WHERE ledger_id = ?", (ledger_id,)).fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def mark_settled(store_dir: str | Path, ledger_id: str, key: str) -> None:
    """Record a delivered (202) key. `INSERT OR IGNORE` never flips a dead-lettered row."""
    conn = _connect(store_dir)
    try:
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO delivery (ledger_id, idempotency_key, status, updated_at) VALUES (?, ?, ?, ?)",
                (ledger_id, key, _DELIVERED, _now()),
            )
    finally:
        conn.close()


# --- dead-letter sink (the row IS the cursor mark — one atomic write) ---


def dead_letter(store_dir: str | Path, ledger_id: str, entry: dict[str, Any]) -> None:
    """Record a terminal-but-skippable event. The single row settles AND dead-letters it."""
    event = entry["event"]
    key = event["idempotency_key"]
    conn = _connect(store_dir)
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO delivery "
                "(ledger_id, idempotency_key, status, reason, event_json, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (ledger_id, key, _DEAD_LETTERED, entry.get("reason"), json.dumps(event), _now()),
            )
    finally:
        conn.close()


def load_dead_letter(store_dir: str | Path, ledger_id: str) -> list[dict[str, Any]]:
    conn = _connect(store_dir)
    try:
        rows = conn.execute(
            "SELECT event_json, reason FROM delivery WHERE ledger_id = ? AND status = ? ORDER BY rowid",
            (ledger_id, _DEAD_LETTERED),
        ).fetchall()
    finally:
        conn.close()
    return [{"event": json.loads(event_json), "reason": reason} for event_json, reason in rows]


# --- persisted iplanic identity (the worker re-projects with it) ---


def save_identity(store_dir: str | Path, ledger_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Persist the payload's 8 identity fields so a later `sync` can project; return them."""
    identity = {k: payload.get(k) for k in _IDENTITY_FIELDS}
    conn = _connect(store_dir)
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO identity (ledger_id, identity_json) VALUES (?, ?)",
                (ledger_id, json.dumps(identity)),
            )
    finally:
        conn.close()
    return identity


def load_identity(store_dir: str | Path, ledger_id: str) -> dict[str, Any] | None:
    conn = _connect(store_dir)
    try:
        row = conn.execute("SELECT identity_json FROM identity WHERE ledger_id = ?", (ledger_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    data: Any = json.loads(row[0])
    return data if isinstance(data, dict) else None
