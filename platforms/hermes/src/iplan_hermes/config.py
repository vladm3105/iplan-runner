"""Engine configuration: intake mapping, thresholds, secrets, loading.

A minimal seam that later phases extend. Defaults match
framework/intake/INTAKE_CONTRACT.md; override fields to absorb SDD IPLAN schema
drift without touching engine core. Secrets come from the environment only
(see framework/config/CONFIG_CONTRACT.md).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


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


def secrets_from_env(prefix: str = "IOPS_SECRET_", env: Mapping[str, str] | None = None) -> list[str]:
    """Collect secret values from environment variables named `<prefix>*`."""
    environ = env if env is not None else os.environ
    return [v for k, v in environ.items() if k.startswith(prefix) and v]


def load_config(path: str | Path | None = None, env: Mapping[str, str] | None = None) -> Config:
    """Merge a YAML file (non-secret defaults) + env (overrides, secrets)."""
    environ = env if env is not None else os.environ
    data: dict[str, Any] = {}
    if path is not None and Path(path).exists():
        loaded = yaml.safe_load(Path(path).read_text())
        if isinstance(loaded, dict):
            data = loaded

    cfg = Config()
    fields = set(Config.__dataclass_fields__)
    for key, value in data.items():
        # secrets never come from the file
        if key in fields and key not in ("secrets", "signing_key"):
            setattr(cfg, key, value)

    cfg.secrets = secrets_from_env(env=environ)
    signing_key = environ.get("IOPS_SIGNING_KEY")
    if signing_key:
        cfg.signing_key = signing_key
    return cfg
