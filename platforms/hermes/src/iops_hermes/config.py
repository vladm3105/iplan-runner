"""Thin engine configuration (intake field mapping, thresholds).

A minimal seam that later phases extend. Defaults match
framework/intake/INTAKE_CONTRACT.md; override fields to absorb SDD IPLAN schema
drift without touching engine core.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    exec_ready_min: int = 90
    map_source_iplan: str = "document_control.iplan_id"
    map_version: str = "document_control.version"
    map_score: str = "exec_ready.score"
    map_approved: str = "exec_ready.approved"
    map_scope: str = "isolation_scope"
    map_tasks: str = "tasks"
    secrets: list[str] = field(default_factory=list)
    max_retries: int = 0
    backoff_base: float = 0.0
    signing_key: str | None = None


def secrets_from_env(prefix: str = "IOPS_SECRET_") -> list[str]:
    """Collect secret values from environment variables named `<prefix>*`."""
    return [value for name, value in os.environ.items() if name.startswith(prefix) and value]
