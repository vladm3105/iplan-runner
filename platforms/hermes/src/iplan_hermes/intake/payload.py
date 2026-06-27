"""Second intake front door: an Iplanic task payload → `iplan-intake` manifest.

Mirrors `ingest_iplan` (same manifest shape, so the run loop is unchanged) but
maps from an Iplanic runtime task payload and carries an extra `remote_execution`
identity block (ignored by the loop) for later event emission. Iplanic's schema is
never imported; the consumed subset is the vendored mirror
`framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml` (D-0016).

Two front doors share one manifest core (`_build_manifest`):

* `ingest_task_payload(path)` — the file path (CLI `intake --payload` / `sync`),
  checksummed over the file bytes.
* `ingest_task_payload_dict(payload)` — an in-memory dispatched payload (the A2A
  receiver, PLAN-021), checksummed over the `iplan-canonical-json` of the dict so
  the same payload hashes identically across engines and re-dispatch.

`adapt_dispatched_task` rewrites the dispatched payload's **nested**
`context_package.repository` object into the configured workspace path string
before ingest, so isolation (`allowed_roots` → `in_scope`) gets a path, not an
object. The git coordinate carried by that object (`url`/`default_branch`/
`base_ref`) is a PLAN-022 concern (repo → workspace clone).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from ..security.iplan_canonical.canonical import canonical_hash

_REMOTE_IDS = (
    "task_id",
    "run_id",
    "step_id",
    "executor_id",
    "iplan_id",
    "plan_version_id",
    "org_id",
    "project_id",
    "protocol_plan_id",
    "protocol_agent_id",
)


def _build_manifest(payload: dict[str, Any], checksum: str) -> dict[str, Any]:
    """Map a parsed Iplanic task payload + its `source_iplan_checksum` to an
    `iplan-intake` manifest (the shape the run loop consumes)."""
    work_order = payload.get("work_order") or {}
    todos = work_order.get("todos") or []
    context = payload.get("context_package") or {}

    return {
        "metadata": {
            "schema_version": "1.0",
            "document_type": "iplan-intake",
            "framework": "iops",
        },
        "intake_control": {
            "source_iplan": payload.get("iplan_id"),
            "source_iplan_version": payload.get("plan_version_id"),
            "source_iplan_checksum": checksum,
            # Dispatch is the approval: Iplanic only dispatches approved work and
            # owns the EXEC-Ready >= 90 gate; it is not re-derived here.
            "approved": True,
            "exec_ready_score": 90,
        },
        "isolation_scope": {
            "client_id": payload.get("org_id"),
            "project_id": payload.get("project_id"),
            "allowed_roots": [context.get("repository", ".")],
            "forbidden_paths": context.get("forbidden_paths", []),
        },
        "task_graph": [
            {
                "task_id": t.get("todo_id"),
                "title": t.get("description"),
                "depends_on": [],
                # The run loop's `_init_ledger` reads `acceptance.criteria`, so the
                # manifest must carry the dict shape (not a joined string) to be
                # runnable by the receiver (PLAN-021).
                "acceptance": {"criteria": t.get("acceptance_criteria") or []},
            }
            for t in todos
        ],
        "remote_execution": {
            **{k: payload.get(k) for k in _REMOTE_IDS},
            "work_order_id": work_order.get("work_order_id"),
        },
    }


def ingest_task_payload(path: str | Path) -> dict[str, Any]:
    """Front door for a task payload on disk; the checksum covers the file bytes."""
    raw = Path(path).read_bytes()
    checksum = "sha256:" + hashlib.sha256(raw).hexdigest()
    parsed: Any = yaml.safe_load(raw)
    payload: dict[str, Any] = parsed if isinstance(parsed, dict) else {}
    return _build_manifest(payload, checksum)


def ingest_task_payload_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Front door for an in-memory dispatched payload (the A2A receiver, PLAN-021).

    The checksum is the `iplan-canonical-json` (RFC 8785 + drop-null) sha256 of the
    dict, so a dispatched payload hashes identically regardless of key order or an
    explicit-null vs absent optional — byte-stable across engines (D-0021)."""
    checksum = "sha256:" + canonical_hash(payload)
    return _build_manifest(payload, checksum)


def adapt_dispatched_task(payload: dict[str, Any], *, workspace: str | Path) -> dict[str, Any]:
    """Rewrite the dispatched payload's nested `context_package.repository` object
    (`{url, default_branch, base_ref}`) to the configured `workspace` path string.

    Returns a shallow copy with a fresh `context_package` (the input is not
    mutated); other keys are carried through unchanged. The receiver maps to a
    fixed workspace — the actual repo clone/checkout from the git coordinate is
    PLAN-022."""
    adapted = dict(payload)
    context = dict(adapted.get("context_package") or {})
    context["repository"] = str(workspace)
    adapted["context_package"] = context
    return adapted
