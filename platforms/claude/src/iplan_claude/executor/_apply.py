"""Apply a task action/check spec via the sandboxed effectors + evidence runner.

Shared by ScriptedExecutor (pre-written spec) and ApiExecutor (model-generated
spec) — both produce the same typed action schema (SECURITY_MODEL: output is data).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..effectors.apply import apply_write
from ..effectors.commands import run_command
from ..evidence.runner import run_checks
from .base import ExecutorResult


def apply_task_spec(
    spec: dict[str, Any],
    workspace: str | Path,
    allowed_roots: list[str],
    secrets: list[str],
) -> ExecutorResult:
    touched: list[str] = []
    for action in spec.get("actions", []):
        try:
            if action["type"] == "write":
                touched.append(apply_write(action["path"], action.get("content", ""), workspace, allowed_roots))
            elif action["type"] == "command":
                outcome = run_command(action["cmd"], workspace)
                if outcome["exit_code"] != 0:
                    return ExecutorResult(
                        outcome="failure",
                        touched_paths=touched,
                        reason=f"command failed: {action['cmd']}",
                    )
        except PermissionError as exc:
            return ExecutorResult(outcome="failure", touched_paths=touched, reason=str(exc))

    checks = spec.get("checks", [])
    if not checks:
        return ExecutorResult(outcome="success", touched_paths=touched, evidence=None)

    result = run_checks(checks, workspace, secrets)
    passed = sum(1 for r in result["results"] if r["exit_code"] == 0)
    evidence = {
        "kind": "test",
        "summary": f"{passed}/{len(result['results'])} checks passed",
        "location": "workspace",
    }
    if not result["passed"]:
        return ExecutorResult(outcome="failure", touched_paths=touched, evidence=evidence, reason="checks failed")
    return ExecutorResult(outcome="success", touched_paths=touched, evidence=evidence)
