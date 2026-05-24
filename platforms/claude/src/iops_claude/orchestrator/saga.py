"""Saga helpers: bounded retry, backoff, idempotency (see SAGA_EXECUTION_MODEL)."""
from __future__ import annotations

from typing import Any, Callable

from ..executor.base import ExecutionContext, Executor, ExecutorResult


def backoff(attempt: int, base: float) -> float:
    return float(base * (2 ** (attempt - 1)))


def already_committed(ledger: dict[str, Any], idempotency_key: str) -> bool:
    return any(
        txn.get("idempotency_key") == idempotency_key and txn.get("status") == "committed"
        for txn in ledger.get("saga_journal", [])
    )


def execute_with_retry(
    executor: Executor,
    task_node: dict[str, Any],
    ctx: ExecutionContext,
    *,
    sleep: Callable[[float], None],
    max_retries: int,
    backoff_base: float,
) -> tuple[ExecutorResult, int]:
    attempt = 0
    while True:
        attempt += 1
        result = executor.execute(task_node, ctx)
        if result.outcome == "success":
            return result, attempt
        if result.retriable and attempt <= max_retries:
            sleep(backoff(attempt, backoff_base))
            continue
        return result, attempt
