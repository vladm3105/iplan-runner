"""Effectors, evidence runner, redaction, ScriptedExecutor (Hermes)."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from iops_hermes import HermesEngine
from iops_hermes.effectors.apply import apply_write
from iops_hermes.effectors.commands import run_command
from iops_hermes.effectors.sandbox import classify_path
from iops_hermes.evidence.runner import run_checks
from iops_hermes.executor.base import IdSource
from iops_hermes.redaction import redact

ROOT = Path(__file__).resolve().parents[3]
SANDBOX = ROOT / "framework" / "conformance" / "sandbox"

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


@pytest.mark.parametrize("case", sorted(p.name for p in SANDBOX.iterdir()))
def test_classify_path_vectors(case: str) -> None:
    inp = yaml.safe_load((SANDBOX / case / "input.yaml").read_text())
    expect = yaml.safe_load((SANDBOX / case / "expect.yaml").read_text())
    assert classify_path(inp["path"], inp["allowed_roots"], inp.get("forbidden_paths", [])) == expect


def test_apply_write_and_denied(tmp_path: Path) -> None:
    apply_write("src/a.py", "print('hi')\n", tmp_path, ["src/"])
    assert (tmp_path / "src" / "a.py").read_text() == "print('hi')\n"
    with pytest.raises(PermissionError):
        apply_write("../evil.py", "x", tmp_path, ["src/"])


def test_run_command(tmp_path: Path) -> None:
    out = run_command(["python", "-c", "print('hello')"], tmp_path)
    assert out["exit_code"] == 0
    assert "hello" in out["output"]


def test_run_checks_pass_and_fail(tmp_path: Path) -> None:
    ok = run_checks([{"name": "t", "command": ["python", "-c", "import sys; sys.exit(0)"]}], tmp_path)
    assert ok["passed"] is True
    bad = run_checks([{"name": "t", "command": ["python", "-c", "import sys; sys.exit(1)"]}], tmp_path)
    assert bad["passed"] is False


def test_redact() -> None:
    assert redact("token=abc123 key=abc", ["abc123", "abc"]) == "token=*** key=***"


def test_scripted_executor_end_to_end(tmp_path: Path) -> None:
    engine = HermesEngine()
    spec = {
        "T1": {
            "actions": [{"type": "write", "path": "src/a.py", "content": "x\n"}],
            "checks": [{"name": "ok", "command": ["python", "-c", "import sys; sys.exit(0)"]}],
        }
    }
    result = engine.run(MANIFEST, engine.scripted_executor(spec, tmp_path), clock=_clock(), ids=IdSource())
    t1 = result.ledger["task_ledger"][0]
    assert t1["status"] == "completed"
    assert t1["evidence_refs"]
    assert result.gate_result["status"] == "passed"
    assert engine.build_handover(result.ledger, result.gate_result)["result"]["status"] == "completed"
    assert (tmp_path / "src" / "a.py").exists()


def test_scripted_executor_sandbox_denied(tmp_path: Path) -> None:
    engine = HermesEngine()
    spec = {"T1": {"actions": [{"type": "write", "path": "../evil.py", "content": "x"}]}}
    result = engine.run(MANIFEST, engine.scripted_executor(spec, tmp_path), clock=_clock(), ids=IdSource())
    assert result.ledger["task_ledger"][0]["status"] == "blocked"
    assert not (tmp_path.parent / "evil.py").exists()
