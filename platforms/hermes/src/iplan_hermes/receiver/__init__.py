"""Inbound A2A task receiver (PLAN-021): the `POST /v1/tasks` door.

Opt-in (`receiver.enabled`), stdlib-only, gated out of CI. Accepts an iplanic
A2A `task.schema.json` dispatch under a mandatory bearer, ACKs `202` promptly,
runs a deterministic executor through intake → orchestrator → relay back to
iplanic, stays dispatchable via a heartbeat, and is idempotent on
`(run_id, task_id)`.
"""

from __future__ import annotations

from .auth import verify_bearer
from .heartbeat import Heartbeat
from .http import ReceiverServer, build_receiver
from .service import ReceiverDeps, execute

__all__ = [
    "Heartbeat",
    "ReceiverDeps",
    "ReceiverServer",
    "build_receiver",
    "execute",
    "verify_bearer",
]
