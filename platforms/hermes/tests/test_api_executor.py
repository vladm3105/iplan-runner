"""hermes ApiExecutor over a StubModelClient (autonomous, offline)."""
from __future__ import annotations

import itertools
import json
from collections.abc import Callable
from pathlib import Path

from iops_hermes import HermesEngine
from iops_hermes.budget import Budget
from iops_hermes.executor.base import IdSource
from iops_hermes.model.client import StubModelClient

MANIFEST = {
    "metadata": {"schema_version": "1.0", "document_type": "iplan-intake", "framework": "iops"},
    "intake_control": {"source_iplan": "IPLAN-001", "source_iplan_version": "1.0.0",
                       "source_iplan_checksum": "sha256:" + "a" * 64,
                       "exec_ready_score": 92, "approved": True},
    "isolation_scope": {"client_id": "c", "project_id": "p", "allowed_roots": ["src/"]},
    "task_graph": [{"task_id": "T1", "title": "do", "depends_on": [], "acceptance": {"criteria": ["x"]}}],
}


def _clock() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"2026-05-24T10:{next(counter):02d}:00Z"


def _noop_sleep(_s: float) -> None:
    return None


def _run(engine: HermesEngine, client: StubModelClient, tmp: Path, budget: Budget | None = None):
    executor = engine.api_executor(client, tmp, budget)
    return engine.run(MANIFEST, executor, clock=_clock(), ids=IdSource(), sleep=_noop_sleep)


def test_api_executor_applies_model_actions(tmp_path: Path) -> None:
    engine = HermesEngine()
    response = json.dumps({
        "actions": [{"type": "write", "path": "src/a.py", "content": "x\n"}],
        "checks": [{"name": "ok", "command": ["python", "-c", "import sys; sys.exit(0)"]}],
    })
    result = _run(engine, StubModelClient(response, {"tokens": 5}), tmp_path)
    assert result.ledger["task_ledger"][0]["status"] == "completed"
    assert (tmp_path / "src" / "a.py").exists()
    assert result.gate_result["status"] == "passed"


def test_api_executor_blocks_out_of_scope(tmp_path: Path) -> None:
    engine = HermesEngine()
    response = json.dumps({"actions": [{"type": "write", "path": "../evil.py", "content": "x"}]})
    result = _run(engine, StubModelClient(response), tmp_path)
    assert result.ledger["task_ledger"][0]["status"] == "blocked"
    assert not (tmp_path.parent / "evil.py").exists()


def test_api_executor_unparseable_output_blocks(tmp_path: Path) -> None:
    engine = HermesEngine()
    result = _run(engine, StubModelClient("not json"), tmp_path)
    assert result.ledger["task_ledger"][0]["status"] == "blocked"


def test_api_executor_budget_exceeded_blocks(tmp_path: Path) -> None:
    engine = HermesEngine()
    response = json.dumps({"actions": [{"type": "write", "path": "src/a.py", "content": "x"}]})
    result = _run(engine, StubModelClient(response, {"tokens": 100}), tmp_path, Budget(max_tokens=10))
    assert result.ledger["task_ledger"][0]["status"] == "blocked"
    assert "budget" in (result.ledger["task_ledger"][0]["blocked_reason"] or "")
