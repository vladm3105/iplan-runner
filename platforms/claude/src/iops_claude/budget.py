"""Resource budget + pure enforcement decision (see RESOURCE_GOVERNANCE.md)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
