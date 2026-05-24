"""Thin engine configuration (intake field mapping, thresholds).

A minimal seam that later phases extend. Defaults match
framework/intake/INTAKE_CONTRACT.md; override fields to absorb SDD IPLAN schema
drift without touching engine core.
"""
from __future__ import annotations

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
