"""Run a dispatched task: claim → adapt → ingest → run → drain → settle (PLAN-021).

The HTTP handler durably accepts a task and ACKs `202`; this module is the
background half. It first **claims** the run (an atomic `accepted` -> `running`
transition) so that two concurrent acceptors never both run, then maps the
dispatched payload to the run manifest, runs a **deterministic** executor, and
drains the resulting signed ledger back to iplanic through the existing relay
worker. The terminal status (`done`/`failed`) is recorded on the accept row; a
drain that does not fully settle leaves its events in the ledger for the operator
`sync` to re-drain (PLAN-022 adds auto re-drain).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..engine import ClaudeEngine, _default_clock
from ..executor.base import IdSource
from ..intake.payload import adapt_dispatched_task, ingest_task_payload_dict
from ..ledger.persistence import save
from ..relay import store
from ..relay.client import IplanicClient
from ..relay.worker import drain


def _noop(_message: str) -> None:
    return None


@dataclass
class ReceiverDeps:
    """Everything `execute` needs, wired once and shared across worker threads."""

    engine: ClaudeEngine
    store_dir: str
    workspace: str
    client: IplanicClient
    key: bytes
    key_id: str | None = None
    log: Callable[[str], None] = field(default=_noop)


def execute(payload: dict[str, Any], deps: ReceiverDeps) -> None:
    """Claim, run, and drain one dispatched task. Never raises — a failure is
    recorded on the accept row and logged (the worker thread must not crash)."""
    run_id: str = payload["run_id"]  # presence guaranteed by validate_payload at the door
    task_id: str = payload["task_id"]
    if not store.claim_task(deps.store_dir, run_id, task_id):
        deps.log(f"claim-lost run={run_id} task={task_id}")  # a concurrent acceptor won the run
        return
    deps.log(f"run-start run={run_id} task={task_id}")
    try:
        adapted = adapt_dispatched_task(payload, workspace=deps.workspace)
        manifest = ingest_task_payload_dict(adapted)
        run_result = deps.engine.run(manifest, deps.engine.default_executor(), clock=_default_clock, ids=IdSource())
        ledger = run_result.ledger
        ledger_id = ledger["ledger_control"]["ledger_id"]
        save(ledger, deps.store_dir)
        identity = store.save_identity(deps.store_dir, ledger_id, payload)
        report = drain(
            ledger,
            identity,
            client=deps.client,
            store_dir=deps.store_dir,
            ledger_id=ledger_id,
            key=deps.key,
            key_id=deps.key_id,
        )
        store.settle_task(deps.store_dir, run_id, task_id, ok=report.ok)
        deps.log(
            f"run-done run={run_id} task={task_id} ledger={ledger_id} "
            f"delivered={len(report.delivered)} pending={len(report.pending)} ok={report.ok}"
        )
    except Exception as exc:  # noqa: BLE001 - record + log; a worker thread must never crash the server
        store.settle_task(deps.store_dir, run_id, task_id, ok=False)
        deps.log(f"error run={run_id} task={task_id}: {exc!r}")
