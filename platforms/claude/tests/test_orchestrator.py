"""Run loop, topo order, persistence (Claude)."""
from __future__ import annotations

import itertools
from pathlib import Path
from typing import Callable

from iops_claude import ClaudeEngine
from iops_claude.executor.base import IdSource
from iops_claude.ledger.index import list_runs, status
from iops_claude.ledger.persistence import ledger_path, load, save
from iops_claude.ledger.store import verify_chain
from iops_claude.orchestrator.topo import topo_order

MANIFEST = {
    "metadata": {"schema_version": "1.0", "document_type": "iplan-intake", "framework": "iops"},
    "intake_control": {
        "source_iplan": "IPLAN-001",
        "source_iplan_version": "1.0.0",
        "source_iplan_checksum": "sha256:" + "a" * 64,
        "exec_ready_score": 92,
        "approved": True,
    },
    "isolation_scope": {"client_id": "client-a", "project_id": "project-x", "allowed_roots": ["src/"]},
    "task_graph": [
        {"task_id": "T1", "title": "a", "depends_on": [], "acceptance": {"criteria": ["x"]}},
        {"task_id": "T2", "title": "b", "depends_on": ["T1"], "acceptance": {"criteria": ["y"]}},
    ],
}

EVIDENCE = {"kind": "test", "summary": "ok", "location": "ci://1"}


def _clock() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"2026-05-24T10:{next(counter):02d}:00Z"


def _task(ledger: dict, task_id: str) -> dict:
    return next(t for t in ledger["task_ledger"] if t["task_id"] == task_id)


def test_topo_order() -> None:
    assert topo_order(MANIFEST["task_graph"]) == ["T1", "T2"]


def test_run_all_success() -> None:
    engine = ClaudeEngine()
    outcomes = {
        "T1": {"outcome": "success", "touched_paths": ["src/a.py"], "evidence": EVIDENCE},
        "T2": {"outcome": "success", "touched_paths": ["src/b.py"], "evidence": EVIDENCE},
    }
    result = engine.run(MANIFEST, engine.mock_executor(outcomes), clock=_clock(), ids=IdSource())
    assert verify_chain(result.ledger["execution_log"]) is True
    assert _task(result.ledger, "T1")["status"] == "completed"
    assert _task(result.ledger, "T2")["status"] == "completed"
    assert result.ledger["reconciliation"]["allowed"] is True
    assert result.gate_result["status"] == "passed"
    assert engine.build_handover(result.ledger, result.gate_result)["result"]["status"] == "completed"


def test_run_failure_blocks() -> None:
    engine = ClaudeEngine()
    outcomes = {"T1": {"outcome": "failure", "reason": "tests failed"}}
    result = engine.run(MANIFEST, engine.mock_executor(outcomes), clock=_clock(), ids=IdSource())
    assert _task(result.ledger, "T1")["status"] == "blocked"
    assert result.ledger["reconciliation"]["allowed"] is False
    # gate validates well-formedness: a blocked task with an owner is well-formed
    assert result.gate_result["status"] == "passed"
    assert engine.build_handover(result.ledger, result.gate_result)["result"]["status"] == "aborted"


def test_gate_veto_on_missing_evidence() -> None:
    engine = ClaudeEngine()
    # success but no evidence -> optimistic complete -> gate must veto
    outcomes = {
        "T1": {"outcome": "success", "touched_paths": ["src/a.py"]},
        "T2": {"outcome": "success", "touched_paths": ["src/b.py"]},
    }
    result = engine.run(MANIFEST, engine.mock_executor(outcomes), clock=_clock(), ids=IdSource())
    assert result.ledger["reconciliation"]["allowed"] is True
    assert result.gate_result["status"] == "failed"
    assert engine.build_handover(result.ledger, result.gate_result)["result"]["status"] == "aborted"


def test_persistence_roundtrip(tmp_path: Path) -> None:
    engine = ClaudeEngine()
    outcomes = {"T1": {"outcome": "success", "evidence": EVIDENCE},
                "T2": {"outcome": "success", "evidence": EVIDENCE}}
    result = engine.run(MANIFEST, engine.mock_executor(outcomes), clock=_clock(), ids=IdSource())
    path = save(result.ledger, tmp_path)
    assert path == ledger_path(tmp_path, "LEDGER-IPLAN-001")
    assert load(path) == result.ledger
    assert list_runs(tmp_path) == ["LEDGER-IPLAN-001"]
    assert status("LEDGER-IPLAN-001", tmp_path)["tasks"] == {"completed": 2}
