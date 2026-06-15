"""Project the signed execution ledger into Iplanic `execution-event`s.

A pure projection of the already-signed `execution_log` into Iplanic's event shape
(REMOTE_EXECUTOR_CONTRACT.md): engine `agent_id` is dropped, the payload's
`executor_id` is used, and each event is signed with the `iplan-canonical-json`
signer (D-0017) so Iplanic can reproduce the signature. Identity + injected ids
only — never engine identity — so both engines emit byte-identical events.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..security.iplanic_signing import sign, signing_payload


def _ident(run_id: str, event_hash: str, event_type: str) -> tuple[str, str, str]:
    """Derive (idempotency_key, event_id, trace_id) from the hash-chain identity.

    Anchored on the D-0008 ``event_hash`` (not a positional counter) so
    re-projection is byte-stable and Iplanic's ``idempotency_key`` dedup holds.
    The ``event_type`` discriminator separates the two events a single
    ``task_completed`` log entry fans out to (``task.completed`` + ``test.*``),
    which share one ``event_hash``. ``trace_id`` groups the per-log-event fan-out.
    """
    idem = f"{run_id}:{event_hash}:{event_type}"
    event_id = "EV-" + hashlib.sha256(idem.encode()).hexdigest()[:12]
    trace_id = "TR-" + hashlib.sha256(f"{run_id}:{event_hash}".encode()).hexdigest()[:12]
    return idem, event_id, trace_id


#: real `execution_log` kinds → (Iplanic event_type, status)
_EVENT_MAP: dict[str, tuple[str, str]] = {
    "task_started": ("task.started", "running"),
    "file_edited": ("file.changed", "running"),
    "task_completed": ("task.completed", "succeeded"),
    "task_blocked": ("task.blocked", "blocked"),
    "commit": ("artifact.created", "running"),
}
#: saga undo / blocker override have no Iplanic event_type — deliberately skipped.
_SKIP = {"compensation", "resolution"}

_IDENTITY_FIELDS = (
    "org_id",
    "project_id",
    "iplan_id",
    "plan_version_id",
    "run_id",
    "task_id",
    "step_id",
    "executor_id",
)


def _build_event(
    identity: dict[str, Any],
    event_type: str,
    status: str,
    occurred_at: str,
    artifact_refs: list[str],
    key: bytes,
    key_id: str,
    event_hash: str,
) -> dict[str, Any]:
    idempotency_key, event_id, trace_id = _ident(identity["run_id"], event_hash, event_type)
    event: dict[str, Any] = {
        **identity,
        "trace_id": trace_id,
        "event_id": event_id,
        "idempotency_key": idempotency_key,
        "event_type": event_type,
        "occurred_at": occurred_at,
        # offline: Iplanic overwrites received_at on ingest (Clock-Skew Window).
        "received_at": occurred_at,
        "status": status,
        "artifact_refs": artifact_refs,
    }
    value = sign(signing_payload(event), algorithm="hmac-sha256", key=key)
    event["signature"] = {"key_id": key_id, "algorithm": "hmac-sha256", "value": value}
    return event


def to_execution_events(
    ledger: dict[str, Any],
    payload: dict[str, Any],
    *,
    key: bytes,
    key_id: str,
) -> list[dict[str, Any]]:
    identity = {k: payload.get(k) for k in _IDENTITY_FIELDS}
    results = {t.get("task_id"): (t.get("acceptance") or {}).get("result") for t in ledger.get("task_ledger", [])}
    events: list[dict[str, Any]] = []
    for log_event in ledger.get("execution_log", []):
        kind = log_event.get("event_type")
        if kind in _SKIP or kind not in _EVENT_MAP:
            continue
        event_type, status = _EVENT_MAP[kind]
        event_hash = log_event["event_hash"]
        events.append(
            _build_event(
                identity,
                event_type,
                status,
                log_event["at"],
                log_event.get("touched_paths") or [],
                key,
                key_id,
                event_hash,
            )
        )
        if kind == "task_completed":
            passed = results.get(log_event.get("subject_id")) == "pass"
            events.append(
                _build_event(
                    identity,
                    "test.passed" if passed else "test.failed",
                    "running",
                    log_event["at"],
                    [],
                    key,
                    key_id,
                    event_hash,
                )
            )
    return events
