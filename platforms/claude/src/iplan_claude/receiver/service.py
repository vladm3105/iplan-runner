"""Run a dispatched task: claim → adapt → ingest → run → drain → settle (PLAN-021).

The HTTP handler durably accepts a task and ACKs `202`; this module is the
background half. It first **claims** the run (an atomic `accepted` -> `running`
transition) so that two concurrent acceptors never both run, then maps the
dispatched payload to the run manifest, runs a **deterministic** executor, and
drains the resulting signed ledger back to iplanic through the existing relay
worker. The terminal status (`done`/`failed`) is recorded on the accept row; a
drain that does not fully settle leaves its events in the ledger for the operator
`sync` to re-drain (auto re-drain is a PLAN-023+ follow-on).
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..engine import ClaudeEngine, _default_clock
from ..executor.base import Executor, IdSource
from ..intake.payload import adapt_dispatched_task, ingest_task_payload_dict
from ..ledger.persistence import save
from ..relay import store
from ..relay.client import IplanicClient
from ..relay.worker import drain
from ..vcs.git import clone


def _noop(_message: str) -> None:
    return None


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def _slug(component: str) -> str:
    """Sanitize one path component so a payload-controlled id cannot escape its parent: replace any
    char outside ``[A-Za-z0-9._-]`` with ``_``. Raises ``ValueError`` if the result is empty, ``.``,
    or ``..`` — `run_id`/`task_id` are only non-empty-validated at the door (no charset), so the clone
    dest embeds untrusted strings."""
    slug = _UNSAFE.sub("_", component)
    if slug in ("", ".", ".."):
        raise ValueError(f"unsafe path component: {component!r}")
    return slug


def provision_workspace(payload: dict[str, Any], root: str, *, run_id: str, task_id: str) -> str:
    """Materialize the task's workspace. When the dispatched ``context_package.repository`` is the
    object shape ``{url, default_branch, base_ref}`` (Iplanic's dispatch), clone it at ``base_ref`` into
    a per-run directory ``<root>/<run_id>/<task_id>`` and return that path; when it is a string (the
    file-intake shape) or absent, return ``root`` unchanged — no clone (backward-compatible). The
    ``{url, base_ref}`` fields are guaranteed non-empty strings by the door validation
    (``REMOTE.PAYLOAD_REPOSITORY_SHAPE``)."""
    repo = (payload.get("context_package") or {}).get("repository")
    if not isinstance(repo, dict):
        return str(root)
    dest = Path(root) / _slug(run_id) / _slug(task_id)
    shutil.rmtree(dest, ignore_errors=True)  # a re-run clones fresh (git clone needs a non-existent dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    clone(repo["url"], repo["base_ref"], dest)
    return str(dest)


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
    # The executor is injectable so a real executor can replace the default `MockExecutor` with no
    # receiver change (PLAN-022). Called with the (per-task, possibly cloned) workspace; the default
    # ignores it and returns today's deterministic `MockExecutor`.
    make_executor: Callable[[ClaudeEngine, str], Executor] = field(
        default=lambda engine, _workspace: engine.default_executor()
    )


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
        workspace = provision_workspace(payload, deps.workspace, run_id=run_id, task_id=task_id)
        adapted = adapt_dispatched_task(payload, workspace=workspace)
        manifest = ingest_task_payload_dict(adapted)
        run_result = deps.engine.run(
            manifest, deps.make_executor(deps.engine, workspace), clock=_default_clock, ids=IdSource()
        )
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
