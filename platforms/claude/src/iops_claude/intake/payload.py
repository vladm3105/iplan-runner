"""Second intake front door: an Iplanic task payload → `iplan-intake` manifest.

Mirrors `ingest_iplan` (same manifest shape, so the run loop is unchanged) but
maps from an Iplanic runtime task payload and carries an extra `remote_execution`
identity block (ignored by the loop) for later event emission. Iplanic's schema is
never imported; the consumed subset is the vendored mirror
`framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml` (D-0016).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

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


def ingest_task_payload(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    checksum = "sha256:" + hashlib.sha256(raw).hexdigest()
    parsed: Any = yaml.safe_load(raw)
    payload: dict[str, Any] = parsed if isinstance(parsed, dict) else {}

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
                "acceptance": "; ".join(t.get("acceptance_criteria") or []),
            }
            for t in todos
        ],
        "remote_execution": {
            **{k: payload.get(k) for k in _REMOTE_IDS},
            "work_order_id": work_order.get("work_order_id"),
        },
    }
