"""Chain orchestration: order, linear, upstream block, control (Claude)."""
from __future__ import annotations

import itertools
from collections.abc import Callable

from iops_claude import ClaudeEngine
from iops_claude.executor.base import IdSource
from iops_claude.orchestrator.chain import chain_order

EV = {"kind": "test", "summary": "ok", "location": "ci://1"}
CHAIN = {
    "chain_id": "CHAIN-001",
    "iplan_chain": [
        {"iplan_id": "IPLAN-001", "order": 1, "depends_on": []},
        {"iplan_id": "IPLAN-002", "order": 2, "depends_on": ["IPLAN-001"]},
    ],
    "execution_tiers": [], "cross_plan_leases": [],
}


def _manifest(source: str) -> dict:
    return {
        "metadata": {"schema_version": "1.0", "document_type": "iplan-intake", "framework": "iops"},
        "intake_control": {"source_iplan": source, "source_iplan_version": "1.0.0",
                           "source_iplan_checksum": "sha256:" + "a" * 64,
                           "exec_ready_score": 92, "approved": True},
        "isolation_scope": {"client_id": "c", "project_id": "p", "allowed_roots": ["src/"]},
        "task_graph": [{"task_id": "T1", "title": "do", "depends_on": [], "acceptance": {"criteria": ["x"]}}],
    }


IPLANS = {"IPLAN-001": _manifest("IPLAN-001"), "IPLAN-002": _manifest("IPLAN-002")}


def _clock() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"2026-05-24T10:{next(counter):02d}:00Z"


def _noop_sleep(_s: float) -> None:
    return None


def _control(states: list[str]) -> Callable[[], str]:
    it = iter(states)
    return lambda: next(it, "running")


def _exec_for(outcomes: dict) -> Callable[[str], object]:
    engine = ClaudeEngine()
    return lambda iid: engine.mock_executor(outcomes.get(iid, {}))


def test_chain_order() -> None:
    assert chain_order(CHAIN["iplan_chain"]) == ["IPLAN-001", "IPLAN-002"]


def test_chain_linear_reconciles() -> None:
    engine = ClaudeEngine()
    outcomes = {"IPLAN-001": {"T1": {"outcome": "success", "evidence": EV}},
                "IPLAN-002": {"T1": {"outcome": "success", "evidence": EV}}}
    result = engine.run_chain(CHAIN, IPLANS, _exec_for(outcomes),
                              clock=_clock(), ids=IdSource(), sleep=_noop_sleep)
    flags = {n["iplan_id"]: n["reconciled"] for n in result.chain_ledger["iplan_chain"]}
    assert flags == {"IPLAN-001": True, "IPLAN-002": True}
    assert result.chain_ledger["chain_reconciliation"]["allowed"] is True


def test_chain_upstream_block() -> None:
    engine = ClaudeEngine()
    outcomes = {"IPLAN-001": {"T1": {"outcome": "failure", "reason": "boom"}},
                "IPLAN-002": {"T1": {"outcome": "success", "evidence": EV}}}
    result = engine.run_chain(CHAIN, IPLANS, _exec_for(outcomes),
                              clock=_clock(), ids=IdSource(), sleep=_noop_sleep)
    flags = {n["iplan_id"]: n["reconciled"] for n in result.chain_ledger["iplan_chain"]}
    assert flags == {"IPLAN-001": False, "IPLAN-002": False}
    assert "IPLAN-002" not in result.sub_ledgers  # not run (upstream unreconciled)
    assert result.chain_ledger["chain_reconciliation"]["allowed"] is False


def test_chain_control_abort() -> None:
    engine = ClaudeEngine()
    outcomes = {"IPLAN-001": {"T1": {"outcome": "success", "evidence": EV}},
                "IPLAN-002": {"T1": {"outcome": "success", "evidence": EV}}}
    result = engine.run_chain(CHAIN, IPLANS, _exec_for(outcomes),
                              clock=_clock(), ids=IdSource(), sleep=_noop_sleep,
                              control=_control(["running", "aborted"]))
    assert "IPLAN-001" in result.sub_ledgers
    assert "IPLAN-002" not in result.sub_ledgers
