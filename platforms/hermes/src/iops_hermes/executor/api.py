"""Autonomous executor: a model proposes the actions (hermes A-style, D-0013)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..budget import Budget, check
from ..effectors.compensate import undo_writes
from ..model.client import ModelClient
from ._apply import apply_task_spec
from .base import ExecutionContext, ExecutorResult


def build_prompt(task: dict[str, Any]) -> str:
    return (
        f"Task {task.get('task_id')}: {task.get('title')}\n"
        f"Acceptance: {task.get('acceptance')}\n"
        "Respond with JSON {\"actions\": [...], \"checks\": [...]}."
    )


def parse_actions(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


class ApiExecutor:
    def __init__(
        self,
        client: ModelClient,
        workspace: str | Path = ".",
        budget: Budget | None = None,
        secrets: list[str] | None = None,
    ) -> None:
        self._client = client
        self._workspace = Path(workspace)
        self._budget = budget or Budget()
        self._secrets = secrets or []
        self._usage: dict[str, Any] = {"tokens": 0, "cost_usd": 0.0, "wall_s": 0.0}

    def execute(self, task: dict[str, Any], ctx: ExecutionContext) -> ExecutorResult:
        pre = check(self._budget, self._usage)
        if not pre["allowed"]:
            return ExecutorResult(outcome="failure", reason=f"budget: {pre['reason']}")

        response = self._client.complete(build_prompt(task))
        self._usage["tokens"] += int(response.usage.get("tokens", 0))
        self._usage["cost_usd"] += float(response.usage.get("cost_usd", 0.0))

        post = check(self._budget, self._usage)
        if not post["allowed"]:
            return ExecutorResult(outcome="failure", reason=f"budget: {post['reason']}")

        spec = parse_actions(response.text)
        if spec is None:
            return ExecutorResult(outcome="failure", reason="unparseable model output")
        roots = list(ctx.isolation_scope.get("allowed_roots", []))
        return apply_task_spec(spec, self._workspace, roots, self._secrets)

    def compensate(self, touched_paths: list[str]) -> None:
        undo_writes(touched_paths, self._workspace)
