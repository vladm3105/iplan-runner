"""Resource budget + pure enforcement decision (see RESOURCE_GOVERNANCE.md)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

_T = TypeVar("_T")


class DeadlineExceeded(Exception):
    """A wrapped call exceeded its wall-clock budget (maps to BUDGET.TIME_EXCEEDED)."""


def run_with_deadline(fn: Callable[[], _T], max_wall_s: float | None) -> _T:
    """Run ``fn`` under a wall-clock deadline (M-wall, PLAN-025 P3). With
    ``max_wall_s is None`` it runs inline (no timeout, no thread). Otherwise it runs on
    a **daemon** worker thread and raises ``DeadlineExceeded`` if the worker does not
    finish in time — the hung worker is then abandoned (daemon, so it never blocks
    interpreter exit), which frees the caller and, up the stack, the receiver slot the
    task was holding. A worker exception is re-raised to the caller. Note: abandoning
    the thread does not kill the underlying work (e.g. a subprocess/HTTP call keeps
    running orphaned) — only the slot is reclaimed."""
    if max_wall_s is None:
        return fn()
    result: list[_T] = []
    error: list[BaseException] = []

    def _worker() -> None:
        try:
            result.append(fn())
        except BaseException as exc:  # noqa: BLE001 - re-raised to the caller below
            error.append(exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(max_wall_s)
    if thread.is_alive():
        raise DeadlineExceeded
    if error:
        raise error[0]
    return result[0]


@dataclass
class Budget:
    max_tokens: int | None = None
    max_cost_usd: float | None = None
    max_wall_s: float | None = None


def check(budget: Budget | dict[str, Any], usage: dict[str, Any]) -> dict[str, Any]:
    if isinstance(budget, Budget):
        max_tokens, max_cost, max_wall = (
            budget.max_tokens,
            budget.max_cost_usd,
            budget.max_wall_s,
        )
    else:
        max_tokens = budget.get("max_tokens")
        max_cost = budget.get("max_cost_usd")
        max_wall = budget.get("max_wall_s")

    if max_tokens is not None and usage.get("tokens", 0) > max_tokens:
        return {"allowed": False, "reason": "BUDGET.TOKENS_EXCEEDED"}
    if max_cost is not None and usage.get("cost_usd", 0) > max_cost:
        return {"allowed": False, "reason": "BUDGET.COST_EXCEEDED"}
    if max_wall is not None and usage.get("wall_s", 0) > max_wall:
        return {"allowed": False, "reason": "BUDGET.TIME_EXCEEDED"}
    return {"allowed": True, "reason": "BUDGET.OK"}
