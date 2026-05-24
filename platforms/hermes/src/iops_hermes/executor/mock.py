"""Deterministic mock executor scripted by per-task outcomes (or sequences)."""
from __future__ import annotations

from typing import Any

from .base import ExecutionContext, ExecutorResult


class MockExecutor:
    def __init__(self, outcomes: dict[str, dict[str, Any]] | None = None) -> None:
        self._outcomes = outcomes or {}
        self._calls: dict[str, int] = {}

    def execute(self, task: dict[str, Any], ctx: ExecutionContext) -> ExecutorResult:
        task_id = str(task.get("task_id"))
        spec = self._outcomes.get(task_id, {})
        if "attempts" in spec:
            sequence = spec["attempts"]
            index = self._calls.get(task_id, 0)
            chosen = sequence[min(index, len(sequence) - 1)]
            self._calls[task_id] = index + 1
        else:
            chosen = spec
        return ExecutorResult(
            outcome=chosen.get("outcome", "success"),
            touched_paths=list(chosen.get("touched_paths", [])),
            evidence=chosen.get("evidence"),
            reason=chosen.get("reason"),
            retriable=bool(chosen.get("retriable", False)),
        )

    def compensate(self, touched_paths: list[str]) -> None:
        return None
