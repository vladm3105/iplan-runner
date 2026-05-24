"""Chain orchestration: drive multi-IPLAN chains (see CHAIN_MODEL.md).

Composes the single-IPLAN run loop; one injected clock/ids threads the chain.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..executor.base import Executor
from .loop import RunResult, _running
from .loop import run as _run


@dataclass
class ChainResult:
    chain_ledger: dict[str, Any]
    sub_ledgers: dict[str, dict[str, Any]]


def chain_order(iplan_chain: list[dict[str, Any]]) -> list[str]:
    deps = {str(n["iplan_id"]): {str(d) for d in n.get("depends_on", [])} for n in iplan_chain}
    key = {str(n["iplan_id"]): (n.get("order", 0), str(n["iplan_id"])) for n in iplan_chain}
    remaining = set(deps)
    done: set[str] = set()
    order: list[str] = []
    while remaining:
        ready = sorted((t for t in remaining if deps[t] <= done), key=lambda t: key[t])
        chosen = ready[0] if ready else min(remaining, key=lambda t: key[t])
        order.append(chosen)
        done.add(chosen)
        remaining.discard(chosen)
    return order


def build_chain_ledger(chain: dict[str, Any], reconciled: dict[str, bool]) -> dict[str, Any]:
    nodes = [{**n, "reconciled": reconciled.get(str(n["iplan_id"]), False)} for n in chain["iplan_chain"]]
    allowed = all(reconciled.get(str(n["iplan_id"]), False) for n in chain["iplan_chain"])
    return {
        "metadata": {
            "schema_version": "1.0",
            "document_type": "iplan-chain-ledger",
            "framework": "iops",
        },
        "chain_control": {
            "chain_id": chain.get("chain_id", "CHAIN"),
            "status": "completed" if allowed else "blocked",
        },
        "iplan_chain": nodes,
        "execution_order": chain_order(chain["iplan_chain"]),
        "execution_tiers": chain.get("execution_tiers", []),
        "cross_plan_leases": chain.get("cross_plan_leases", []),
        "chain_gate_results": [],
        "chain_reconciliation": {"allowed": allowed},
    }


def run_chain(
    chain: dict[str, Any],
    iplans: dict[str, dict[str, Any]],
    executor_for: Callable[[str], Executor],
    *,
    clock: Callable[[], str],
    ids: Callable[[str], str],
    sleep: Callable[[float], None],
    control: Callable[[], str] | None = None,
    gate: dict[str, Any] | None = None,
) -> ChainResult:
    ctrl = control or _running
    nodes = {str(n["iplan_id"]): n for n in chain["iplan_chain"]}
    reconciled: dict[str, bool] = {}
    sub_ledgers: dict[str, dict[str, Any]] = {}
    for iplan_id in chain_order(chain["iplan_chain"]):
        if ctrl() in ("aborted", "paused"):
            break
        node = nodes[iplan_id]
        if not all(reconciled.get(str(d)) for d in node.get("depends_on", [])):
            reconciled[iplan_id] = False
            continue
        result: RunResult = _run(
            iplans[iplan_id], executor_for(iplan_id),
            clock=clock, ids=ids, sleep=sleep, gate=gate,
        )
        sub_ledgers[iplan_id] = result.ledger
        reconciled[iplan_id] = bool(result.ledger["reconciliation"]["allowed"])
    return ChainResult(build_chain_ledger(chain, reconciled), sub_ledgers)
