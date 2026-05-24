"""Deterministic mock executor scripted by per-task outcomes."""
from __future__ import annotations

from typing import Any

from .base import ExecutionContext, ExecutorResult


class MockExecutor:
    def __init__(self, outcomes: dict[str, dict[str, Any]] | None = None) -> None:
        self._outcomes = outcomes or {}

    def execute(self, task: dict[str, Any], ctx: ExecutionContext) -> ExecutorResult:
        spec = self._outcomes.get(str(task.get("task_id")), {})
        return ExecutorResult(
            outcome=spec.get("outcome", "success"),
            touched_paths=list(spec.get("touched_paths", [])),
            evidence=spec.get("evidence"),
            reason=spec.get("reason"),
        )
