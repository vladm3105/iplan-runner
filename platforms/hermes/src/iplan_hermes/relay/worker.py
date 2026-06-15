"""Drain the local signed ledger to iplanic with at-least-once durability (D-4b).

A thin, resumable loop over the existing pieces: project the verified ledger to
signed events (`ledger/events.py:to_execution_events`, passing the persisted
identity as the payload — only the 8 identity fields are read), then for each
event past the settled cursor: POST verbatim, classify, and either settle (202),
durably dead-letter **then** settle (terminal-but-skippable), or stop and leave
the rest for the next sync (transient/halt). The dead-letter is committed before
the cursor advances, so no event is dropped silently (R3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..ledger.events import to_execution_events
from . import reject, store
from .client import IplanicClient
from .reject import Outcome


@dataclass
class DrainReport:
    delivered: list[str] = field(default_factory=list)
    dead_lettered: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    halted: str | None = None

    @property
    def ok(self) -> bool:
        return self.halted is None


def drain(
    ledger: dict[str, Any],
    identity: dict[str, Any],
    *,
    client: IplanicClient,
    store_dir: str,
    ledger_id: str,
    key: bytes,
    key_id: str | None = None,
    now: datetime | None = None,
    max_age_s: int = reject.DEFAULT_MAX_AGE_S,
) -> DrainReport:
    """Drain every not-yet-settled projected event to iplanic, in order."""
    stamp = now or datetime.now(UTC)
    resolved_key_id = key_id or identity.get("executor_id") or "default"
    events = to_execution_events(ledger, identity, key=key, key_id=resolved_key_id)
    settled = store.load_settled(store_dir, ledger_id)
    report = DrainReport()
    for event in events:
        idem = event["idempotency_key"]
        if idem in settled:
            continue
        outcome = _deliver_with_refresh(client, event, now=stamp, max_age_s=max_age_s)
        if outcome.action == reject.ADVANCE:
            store.mark_settled(store_dir, ledger_id, idem)
            report.delivered.append(idem)
        elif outcome.action == reject.DEAD_LETTER:
            store.dead_letter(store_dir, ledger_id, {"event": event, "reason": outcome.reason})
            store.mark_settled(store_dir, ledger_id, idem)  # only after the dead-letter commit
            report.dead_lettered.append(idem)
        elif outcome.action == reject.RETRY:
            report.pending.append(idem)
            break  # preserve order — leave this and the rest for the next sync
        else:  # HALT (incl. exhausted refresh)
            report.pending.append(idem)
            report.halted = outcome.reason
            break
    return report


def _deliver_with_refresh(client: IplanicClient, event: dict[str, Any], *, now: datetime, max_age_s: int) -> Outcome:
    """Deliver once; on 401 let the token provider refresh and retry once, then halt."""
    outcome = reject.classify(client.deliver(event), event, now=now, max_age_s=max_age_s)
    if outcome.action == reject.REFRESH:
        outcome = reject.classify(client.deliver(event), event, now=now, max_age_s=max_age_s)
        if outcome.action == reject.REFRESH:
            return Outcome(reject.HALT, "auth refresh failed (401 after refresh)")
    return outcome
