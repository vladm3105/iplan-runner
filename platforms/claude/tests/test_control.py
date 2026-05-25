"""Operator control: abort, pause->resume, override->resume, resolution authz."""
from __future__ import annotations

import itertools
from collections.abc import Callable

import pytest
from iops_claude import ClaudeEngine
from iops_claude.executor.base import IdSource

EV = {"kind": "test", "summary": "ok", "location": "ci://1"}
TASKS = [
    {"task_id": "T1", "title": "a", "depends_on": [], "acceptance": {"criteria": ["x"]}},
    {"task_id": "T2", "title": "b", "depends_on": [], "acceptance": {"criteria": ["y"]}},
]
MANIFEST = {
    "metadata": {"schema_version": "1.0", "document_type": "iplan-intake", "framework": "iops"},
    "intake_control": {"source_iplan": "IPLAN-001", "source_iplan_version": "1.0.0",
                       "source_iplan_checksum": "sha256:" + "a" * 64,
                       "exec_ready_score": 92, "approved": True},
    "isolation_scope": {"client_id": "c", "project_id": "p", "allowed_roots": ["src/"]},
    "task_graph": TASKS,
}
OUTCOMES = {
    "T1": {"outcome": "success", "evidence": EV},
    "T2": {"outcome": "success", "evidence": EV},
}


def _clock() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"2026-05-24T10:{next(counter):02d}:00Z"


def _noop_sleep(_s: float) -> None:
    return None


def _control(states: list[str]) -> Callable[[], str]:
    it = iter(states)
    return lambda: next(it, "running")


def _task(ledger: dict, tid: str) -> dict:
    return next(t for t in ledger["task_ledger"] if t["task_id"] == tid)


def test_abort_stops_before_next_task() -> None:
    engine = ClaudeEngine()
    result = engine.run(MANIFEST, engine.mock_executor(OUTCOMES),
                        clock=_clock(), ids=IdSource(), sleep=_noop_sleep,
                        control=_control(["running", "aborted"]))
    assert result.ledger["ledger_control"]["run_state"] == "aborted"
    assert _task(result.ledger, "T1")["status"] == "completed"
    assert _task(result.ledger, "T2")["status"] == "pending"


def test_pause_then_resume_completes() -> None:
    engine = ClaudeEngine()
    paused = engine.run(MANIFEST, engine.mock_executor(OUTCOMES),
                        clock=_clock(), ids=IdSource(), sleep=_noop_sleep,
                        control=_control(["running", "paused"]))
    assert paused.ledger["ledger_control"]["run_state"] == "paused"
    assert _task(paused.ledger, "T2")["status"] == "pending"

    resumed = engine.resume(MANIFEST, paused.ledger, engine.mock_executor(OUTCOMES),
                            clock=_clock(), ids=IdSource(), sleep=_noop_sleep)
    assert resumed.ledger["ledger_control"]["run_state"] == "completed"
    assert _task(resumed.ledger, "T1")["status"] == "completed"  # not re-run (idempotent)
    assert _task(resumed.ledger, "T2")["status"] == "completed"
    assert resumed.gate_result["status"] == "passed"


def test_override_then_resume_retries_blocked_task() -> None:
    engine = ClaudeEngine()
    outcomes = {"T1": {"outcome": "failure", "reason": "boom"}, "T2": {"outcome": "success", "evidence": EV}}
    blocked = engine.run(MANIFEST, engine.mock_executor(outcomes),
                         clock=_clock(), ids=IdSource(), sleep=_noop_sleep)
    assert _task(blocked.ledger, "T1")["status"] == "blocked"
    blocker_id = blocked.ledger["blockers"][0]["blocker_id"]

    engine.resolve_blocker(blocked.ledger, blocker_id, "override", {"id": "op", "role": "operator"},
                           clock=_clock())
    assert _task(blocked.ledger, "T1")["status"] == "pending"

    good = {"T1": {"outcome": "success", "evidence": EV}, "T2": {"outcome": "success", "evidence": EV}}
    resumed = engine.resume(MANIFEST, blocked.ledger, engine.mock_executor(good),
                            clock=_clock(), ids=IdSource(), sleep=_noop_sleep)
    assert _task(resumed.ledger, "T1")["status"] == "completed"


def test_resolve_requires_operator() -> None:
    engine = ClaudeEngine()
    ledger = {"blockers": [{"blocker_id": "B1", "task_id": "T1"}], "task_ledger": [],
              "isolation_scope": {}, "execution_log": []}
    with pytest.raises(PermissionError):
        engine.resolve_blocker(ledger, "B1", "override", {"id": "a", "role": "agent"}, clock=_clock())
