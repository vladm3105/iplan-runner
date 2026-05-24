"""Executor that performs real effects from a pre-written action script."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..effectors.compensate import undo_writes
from ._apply import apply_task_spec
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
        return apply_task_spec(task_spec, self._workspace, roots, self._secrets)

    def compensate(self, touched_paths: list[str]) -> None:
        undo_writes(touched_paths, self._workspace)
