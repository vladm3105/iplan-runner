"""Executor that performs real effects from a pre-written action script."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..effectors.apply import apply_write
from ..effectors.commands import run_command
from ..effectors.compensate import undo_writes
from ..evidence.runner import run_checks
from .base import ExecutionContext, ExecutorResult


class ScriptedExecutor:
    def __init__(
        self,
        spec: dict[str, Any] | None = None,
        workspace: str | Path = ".",
        secrets: list[str] | None = None,
    ) -> None:
        self._spec = spec or {}
        self._workspace = Path(workspace)
        self._secrets = secrets or []

    def execute(self, task: dict[str, Any], ctx: ExecutionContext) -> ExecutorResult:
        task_spec = self._spec.get(str(task.get("task_id")), {})
        roots = list(ctx.isolation_scope.get("allowed_roots", []))
        touched: list[str] = []

        for action in task_spec.get("actions", []):
            try:
                if action["type"] == "write":
                    touched.append(apply_write(action["path"], action.get("content", ""), self._workspace, roots))
                elif action["type"] == "command":
                    outcome = run_command(action["cmd"], self._workspace)
                    if outcome["exit_code"] != 0:
                        return ExecutorResult(
                            outcome="failure",
                            touched_paths=touched,
                            reason=f"command failed: {action['cmd']}",
                        )
            except PermissionError as exc:
                return ExecutorResult(outcome="failure", touched_paths=touched, reason=str(exc))

        checks = task_spec.get("checks", [])
        if not checks:
            return ExecutorResult(outcome="success", touched_paths=touched, evidence=None)

        result = run_checks(checks, self._workspace, self._secrets)
        passed = sum(1 for r in result["results"] if r["exit_code"] == 0)
        evidence = {
            "kind": "test",
            "summary": f"{passed}/{len(result['results'])} checks passed",
            "location": "workspace",
        }
        if not result["passed"]:
            return ExecutorResult(outcome="failure", touched_paths=touched, evidence=evidence, reason="checks failed")
        return ExecutorResult(outcome="success", touched_paths=touched, evidence=evidence)

    def compensate(self, touched_paths: list[str]) -> None:
        undo_writes(touched_paths, self._workspace)
