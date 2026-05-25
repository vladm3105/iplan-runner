"""Saga retry/compensation/idempotency + lease lifecycle (Claude)."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from pathlib import Path

from iops_claude import ClaudeEngine
from iops_claude.executor.base import IdSource
from iops_claude.orchestrator.leases import can_acquire, lease_state, renew
from iops_claude.orchestrator.saga import already_committed


def _noop_sleep(_seconds: float) -> None:
    return None


EV = {"kind": "test", "summary": "ok", "location": "ci://1"}

MANIFEST = {
    "metadata": {"schema_version": "1.0", "document_type": "iplan-intake", "framework": "iops"},
    "intake_control": {
        "source_iplan": "IPLAN-001",
        "source_iplan_version": "1.0.0",
        "source_iplan_checksum": "sha256:" + "a" * 64,
        "exec_ready_score": 92,
        "approved": True,
    },
    "isolation_scope": {"client_id": "c", "project_id": "p", "allowed_roots": ["src/"]},
    "task_graph": [{"task_id": "T1", "title": "a", "depends_on": [], "acceptance": {"criteria": ["x"]}}],
}


def _clock() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"2026-05-24T10:{next(counter):02d}:00Z"


def _t1(result: object) -> dict:
    return result.ledger["task_ledger"][0]  # type: ignore[attr-defined]


def _txn(result: object, task_id: str) -> dict:
    return next(t for t in result.ledger["saga_journal"] if t["task_id"] == task_id)  # type: ignore[attr-defined]


# --- leases ---


def test_lease_states() -> None:
    now = "2026-05-24T10:30:00Z"
    assert lease_state({"released_at": None, "expires_at": "2026-05-24T11:00:00Z"}, now) == "active"
    assert lease_state({"released_at": None, "expires_at": "2026-05-24T10:00:00Z"}, now) == "expired"
    assert lease_state({"released_at": "2026-05-24T10:15:00Z"}, now) == "released"


def test_can_acquire_and_renew() -> None:
    now = "2026-05-24T10:30:00Z"
    active = {"task_id": "T1", "released_at": None, "expires_at": "2026-05-24T11:00:00Z"}
    assert can_acquire([], "T1", now) is True
    assert can_acquire([active], "T1", now) is False
    assert can_acquire([active], "T2", now) is True
    assert renew(dict(active), "2026-05-24T12:00:00Z")["expires_at"] == "2026-05-24T12:00:00Z"


# --- saga retry ---


def test_retry_then_succeed() -> None:
    engine = ClaudeEngine()
    outcomes = {
        "T1": {
            "attempts": [
                {"outcome": "failure", "retriable": True},
                {"outcome": "success", "touched_paths": ["src/a.py"], "evidence": EV},
            ]
        }
    }
    result = engine.run(
        MANIFEST, engine.mock_executor(outcomes), clock=_clock(), ids=IdSource(), sleep=_noop_sleep, max_retries=2
    )
    assert _t1(result)["status"] == "completed"
    assert _txn(result, "T1")["attempts"] == 2


def test_retry_exhausted_blocks() -> None:
    engine = ClaudeEngine()
    outcomes = {
        "T1": {"attempts": [{"outcome": "failure", "retriable": True}, {"outcome": "failure", "retriable": True}]}
    }
    result = engine.run(
        MANIFEST, engine.mock_executor(outcomes), clock=_clock(), ids=IdSource(), sleep=_noop_sleep, max_retries=1
    )
    assert _t1(result)["status"] == "blocked"
    assert _txn(result, "T1")["attempts"] == 2


def test_no_retry_by_default() -> None:
    engine = ClaudeEngine()
    outcomes = {"T1": {"outcome": "failure", "retriable": True}}
    result = engine.run(MANIFEST, engine.mock_executor(outcomes), clock=_clock(), ids=IdSource(), sleep=_noop_sleep)
    assert _t1(result)["status"] == "blocked"
    assert _txn(result, "T1")["attempts"] == 1


def test_already_committed() -> None:
    ledger = {"saga_journal": [{"idempotency_key": "T1-execute", "status": "committed"}]}
    assert already_committed(ledger, "T1-execute") is True
    assert already_committed(ledger, "T2-execute") is False


# --- compensation (real undo) ---


def test_compensation_undoes_partial_write(tmp_path: Path) -> None:
    engine = ClaudeEngine()
    spec = {
        "T1": {
            "actions": [
                {"type": "write", "path": "src/a.py", "content": "x"},
                {"type": "write", "path": "../evil.py", "content": "x"},
            ]
        }
    }
    result = engine.run(
        MANIFEST, engine.scripted_executor(spec, tmp_path), clock=_clock(), ids=IdSource(), sleep=_noop_sleep
    )
    assert _t1(result)["status"] == "blocked"
    assert _txn(result, "T1")["status"] == "compensated"
    assert not (tmp_path / "src" / "a.py").exists()  # partial write rolled back
    assert any(e["event_type"] == "compensation" for e in result.ledger["execution_log"])
