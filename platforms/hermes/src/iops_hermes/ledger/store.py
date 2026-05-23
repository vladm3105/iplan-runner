"""Append-only ledger store with a hash-chained execution log."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


def compute_event_hash(
    sequence: int,
    previous_event_hash: str | None,
    event_type: str,
    subject_id: str,
    at: str,
) -> str:
    prev = previous_event_hash if previous_event_hash is not None else ""
    payload = f"{sequence}|{prev}|{event_type}|{subject_id}|{at}"
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def verify_chain(execution_log: list[dict[str, Any]]) -> bool:
    """True when sequence, previous_event_hash, and event_hash are consistent."""
    prev_hash: str | None = None
    for index, event in enumerate(execution_log):
        if event.get("sequence") != index + 1:
            return False
        if (event.get("previous_event_hash") or None) != prev_hash:
            return False
        expected = compute_event_hash(
            int(event["sequence"]),
            prev_hash,
            str(event["event_type"]),
            str(event["subject_id"]),
            str(event["at"]),
        )
        if event.get("event_hash") != expected:
            return False
        prev_hash = str(event.get("event_hash"))
    return True


def load_ledger(path: str | Path) -> dict[str, Any]:
    data: Any = yaml.safe_load(Path(path).read_text())
    return data if isinstance(data, dict) else {}


def append_event(ledger: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Append an execution-log event, computing its chained hash. Append-only."""
    log: list[dict[str, Any]] = ledger.setdefault("execution_log", [])
    sequence = len(log) + 1
    previous = str(log[-1]["event_hash"]) if log else None
    new_event = dict(event)
    new_event["sequence"] = sequence
    new_event["previous_event_hash"] = previous
    new_event["event_hash"] = compute_event_hash(
        sequence,
        previous,
        str(new_event["event_type"]),
        str(new_event["subject_id"]),
        str(new_event["at"]),
    )
    log.append(new_event)
    return ledger
