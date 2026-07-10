"""claude HostRuntimeExecutor over a StubRuntimeClient (governor, offline)."""

from __future__ import annotations

import itertools
import threading
from collections.abc import Callable

from iplan_claude import ClaudeEngine
from iplan_claude.budget import Budget
from iplan_claude.executor.base import ExecutionContext, IdSource
from iplan_claude.executor.hostruntime import HostRuntimeExecutor
from iplan_claude.runtime.client import RuntimeResult, StubRuntimeClient

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


def _run(engine: ClaudeEngine, result: RuntimeResult):
    executor = engine.host_executor(StubRuntimeClient(result))
    return engine.run(MANIFEST, executor, clock=_clock(), ids=IdSource(), sleep=_noop_sleep)


def test_host_executor_records_changes() -> None:
    engine = ClaudeEngine()
    result = _run(engine, RuntimeResult(success=True, changed_files=["src/a.py"], output="done"))
    t1 = result.ledger["task_ledger"][0]
    assert t1["status"] == "completed"
    assert t1["evidence_refs"]
    assert result.gate_result["status"] == "passed"


def test_host_executor_failure_blocks() -> None:
    engine = ClaudeEngine()
    result = _run(engine, RuntimeResult(success=False, changed_files=["src/a.py"], output="boom"))
    assert result.ledger["task_ledger"][0]["status"] == "blocked"


def test_host_executor_governs_out_of_scope() -> None:
    engine = ClaudeEngine()
    # runtime touched a path outside allowed_roots -> the engine rejects it
    result = _run(engine, RuntimeResult(success=True, changed_files=["/etc/passwd"], output="x"))
    assert result.ledger["task_ledger"][0]["status"] == "blocked"


def test_host_executor_pre_spend_budget_blocks_without_calling_runtime() -> None:
    # M-budget-parity (PLAN-025 P3): once usage is already over budget, a second
    # task must be refused by a PRE-spend check — the host runtime is never invoked
    # again (matches hermes ApiExecutor). Without the pre-check the runner spends one
    # extra task after the budget is blown.
    calls: list[int] = []

    class _CountingClient:
        def run_task(self, task: dict, workspace: object) -> RuntimeResult:  # type: ignore[type-arg]
            calls.append(1)
            return RuntimeResult(success=True, changed_files=[], output="ok", usage={"tokens": 20})

    executor = HostRuntimeExecutor(_CountingClient(), budget=Budget(max_tokens=10))
    ctx = ExecutionContext(
        task={}, isolation_scope={"allowed_roots": ["src/"]}, clock=lambda: "t", ids=lambda p: p + "1"
    )

    first = executor.execute({"task_id": "T1"}, ctx)  # spends 20 > 10 → post-check fails
    assert first.outcome == "failure"
    assert len(calls) == 1

    second = executor.execute({"task_id": "T2"}, ctx)  # already over budget → pre-check blocks
    assert second.outcome == "failure"
    assert second.reason and "budget" in second.reason
    assert len(calls) == 1  # host runtime NOT invoked a second time


def test_host_executor_wall_timeout_frees_a_hung_runtime_call() -> None:
    # M-wall (PLAN-025 P3): a host-runtime call that outruns max_wall_s is abandoned and
    # the executor returns BUDGET.TIME_EXCEEDED (freeing the run + receiver slot).
    release = threading.Event()

    class _HangingClient:
        def run_task(self, task: dict, workspace: object) -> RuntimeResult:  # type: ignore[type-arg]
            release.wait(timeout=2.0)  # safety cap so the leaked worker cannot outlive the test
            return RuntimeResult(success=True, changed_files=[], output="late")

    executor = HostRuntimeExecutor(_HangingClient(), budget=Budget(max_wall_s=0.1))
    ctx = ExecutionContext(
        task={}, isolation_scope={"allowed_roots": ["src/"]}, clock=lambda: "t", ids=lambda p: p + "1"
    )
    try:
        result = executor.execute({"task_id": "T1"}, ctx)
        assert result.outcome == "failure"
        assert "TIME_EXCEEDED" in (result.reason or "")
    finally:
        release.set()


def test_host_executor_within_wall_budget_succeeds() -> None:
    executor = HostRuntimeExecutor(
        StubRuntimeClient(RuntimeResult(success=True, changed_files=["src/a.py"], output="ok")),
        budget=Budget(max_wall_s=10.0),
    )
    ctx = ExecutionContext(
        task={}, isolation_scope={"allowed_roots": ["src/"]}, clock=lambda: "t", ids=lambda p: p + "1"
    )
    result = executor.execute({"task_id": "T1"}, ctx)
    assert result.outcome == "success"
