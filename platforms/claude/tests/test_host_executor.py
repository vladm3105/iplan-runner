"""claude HostRuntimeExecutor over a StubRuntimeClient (governor, offline)."""

from __future__ import annotations

import itertools
from collections.abc import Callable

from iops_claude import ClaudeEngine
from iops_claude.executor.base import IdSource
from iops_claude.runtime.client import RuntimeResult, StubRuntimeClient

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
