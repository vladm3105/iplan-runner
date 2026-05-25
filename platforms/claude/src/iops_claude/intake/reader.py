"""Normalize an SDD-IPLAN-shaped document into an `iplan-intake` manifest.

Deterministic: the only derived field is the byte sha256 checksum. The field
mapping is configurable (Config) so SDD schema drift is absorbed here, not in the
engine core, and the framework takes no dependency on the SDD repo.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from ..config import Config


def _dig(doc: dict[str, Any], dotted: str) -> Any:
    node: Any = doc
    for key in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def ingest_iplan(path: str | Path, config: Config | None = None) -> dict[str, Any]:
    cfg = config or Config()
    raw = Path(path).read_bytes()
    checksum = "sha256:" + hashlib.sha256(raw).hexdigest()
    parsed: Any = yaml.safe_load(raw)
    doc: dict[str, Any] = parsed if isinstance(parsed, dict) else {}

    scope = _dig(doc, cfg.map_scope)
    tasks = _dig(doc, cfg.map_tasks) or []

    return {
        "metadata": {
            "schema_version": "1.0",
            "document_type": "iplan-intake",
            "framework": "iops",
        },
        "intake_control": {
            "source_iplan": _dig(doc, cfg.map_source_iplan),
            "source_iplan_version": _dig(doc, cfg.map_version),
            "source_iplan_checksum": checksum,
            "exec_ready_score": _dig(doc, cfg.map_score),
            "approved": _dig(doc, cfg.map_approved),
        },
        "isolation_scope": scope if isinstance(scope, dict) else {},
        "task_graph": [
            {
                "task_id": t.get("task_id"),
                "title": t.get("title"),
                "depends_on": t.get("depends_on", []),
                "acceptance": t.get("acceptance"),
            }
            for t in tasks
        ],
    }
