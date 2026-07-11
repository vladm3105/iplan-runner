"""hermes ApiExecutor over a StubModelClient (autonomous, offline)."""

from __future__ import annotations

import itertools
import json
import threading
from collections.abc import Callable
from pathlib import Path

from iplan_hermes import HermesEngine
from iplan_hermes.budget import Budget
from iplan_hermes.executor.api import ApiExecutor
from iplan_hermes.executor.base import ExecutionContext, IdSource
from iplan_hermes.model.client import ModelResponse, StubModelClient

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
    response = json.dumps(
        {
            "actions": [{"type": "write", "path": "src/a.py", "content": "x\n"}],
            "checks": [{"name": "ok", "command": ["python", "-c", "import sys; sys.exit(0)"]}],
        }
    )
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


def _ctx() -> ExecutionContext:
    return ExecutionContext(
        task={}, isolation_scope={"allowed_roots": ["src/"]}, clock=lambda: "t", ids=lambda p: p + "1"
    )


def test_api_executor_wall_timeout_frees_a_hung_model_call() -> None:
    # M-wall (PLAN-025 P3): a model call that outruns max_wall_s is abandoned and the
    # executor returns BUDGET.TIME_EXCEEDED (freeing the run + receiver slot).
    release = threading.Event()

    class _HangingClient:
        def complete(self, prompt: str) -> ModelResponse:
            release.wait(timeout=2.0)  # safety cap so the leaked worker cannot outlive the test
            return ModelResponse(text="{}", usage={})

    executor = ApiExecutor(_HangingClient(), workspace=".", budget=Budget(max_wall_s=0.1))
    try:
        result = executor.execute({"task_id": "T1", "title": "t", "acceptance": {"criteria": ["x"]}}, _ctx())
        assert result.outcome == "failure"
        assert "TIME_EXCEEDED" in (result.reason or "")
    finally:
        release.set()


def test_api_executor_within_wall_budget_succeeds() -> None:
    executor = ApiExecutor(
        StubModelClient(text='{"actions": [], "checks": []}'), workspace=".", budget=Budget(max_wall_s=10.0)
    )
    result = executor.execute({"task_id": "T1", "title": "t", "acceptance": {"criteria": ["x"]}}, _ctx())
    assert result.outcome == "success"
