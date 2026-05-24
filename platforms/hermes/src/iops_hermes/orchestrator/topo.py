"""Deterministic topological ordering of a task graph."""
from __future__ import annotations

from typing import Any


def topo_order(task_graph: list[dict[str, Any]]) -> list[str]:
    """Return task_ids in dependency order, stable tie-break by task_id."""
    deps: dict[str, set[str]] = {
        str(t["task_id"]): set(t.get("depends_on", [])) for t in task_graph
    }
    remaining = set(deps)
    done: set[str] = set()
    order: list[str] = []
    while remaining:
        ready = sorted(tid for tid in remaining if deps[tid] <= done)
        chosen = ready[0] if ready else min(remaining)  # min: break dependency cycles
        order.append(chosen)
        done.add(chosen)
        remaining.discard(chosen)
    return order
