"""Governor executor: drive a host agent runtime, then govern its result.

Claude B-style (D-0013): the host runtime does the work; this executor records
what changed and enforces scope — a runtime that touches a path outside
allowed_roots is rejected (the engine governs the runtime).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..budget import Budget, DeadlineExceeded, check, run_with_deadline
from ..effectors.sandbox import classify_path
from ..runtime.client import RuntimeClient
from .base import ExecutionContext, ExecutorResult


class HostRuntimeExecutor:
    def __init__(
        self,
        client: RuntimeClient,
        workspace: str | Path = ".",
        budget: Budget | None = None,
    ) -> None:
        self._client = client
        self._workspace = Path(workspace)
        self._budget = budget or Budget()
        self._usage: dict[str, Any] = {"tokens": 0, "cost_usd": 0.0, "wall_s": 0.0}

    def execute(self, task: dict[str, Any], ctx: ExecutionContext) -> ExecutorResult:
        # M-budget-parity (PLAN-025 P3): refuse before spending when usage is already
        # over budget, so a blown budget stops the next task instead of running one
        # more (matches hermes ApiExecutor's pre-check).
        pre = check(self._budget, self._usage)
        if not pre["allowed"]:
            return ExecutorResult(outcome="failure", reason=f"budget: {pre['reason']}")

        # M-wall (PLAN-025 P3): bound the host-runtime call by the wall budget so a hung
        # runtime frees the run (and the receiver slot up the stack) instead of blocking.
        started = time.monotonic()
        try:
            result = run_with_deadline(lambda: self._client.run_task(task, self._workspace), self._budget.max_wall_s)
        except DeadlineExceeded:
            self._usage["wall_s"] += time.monotonic() - started
            return ExecutorResult(outcome="failure", reason="budget: BUDGET.TIME_EXCEEDED")
        self._usage["wall_s"] += time.monotonic() - started

        self._usage["tokens"] += int(result.usage.get("tokens", 0))
        self._usage["cost_usd"] += float(result.usage.get("cost_usd", 0.0))
        decision = check(self._budget, self._usage)
        if not decision["allowed"]:
            return ExecutorResult(outcome="failure", reason=f"budget: {decision['reason']}")

        roots = list(ctx.isolation_scope.get("allowed_roots", []))
        for path in result.changed_files:
            if not classify_path(path, roots)["allowed"]:
                return ExecutorResult(
                    outcome="failure",
                    reason=f"host runtime touched out-of-scope path: {path}",
                )

        if not result.success:
            return ExecutorResult(
                outcome="failure",
                touched_paths=list(result.changed_files),
                reason="host runtime reported failure",
            )
        evidence = {"kind": "runtime", "summary": result.output[:200], "location": "workspace"}
        return ExecutorResult(outcome="success", touched_paths=list(result.changed_files), evidence=evidence)

    def compensate(self, touched_paths: list[str]) -> None:
        return None  # the host runtime owns its workspace; compensation is its concern
