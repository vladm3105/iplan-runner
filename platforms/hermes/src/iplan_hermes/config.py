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
    # iplanic sync (D-4b): off by default — standalone/offline is the default mode.
    iplanic_sync_enabled: bool = False
    iplanic_endpoint: str | None = None
    iplanic_token_env: str = "IOPS_IPLANIC_TOKEN"
    iplanic_max_age_s: int = 86400
    # inbound A2A task receiver (PLAN-021): off by default; opt-in, gated out of CI.
    receiver_enabled: bool = False
    receiver_bind: str = "127.0.0.1"
    receiver_port: int = 8080
    receiver_auth_env: str = "IOPS_RECEIVER_TOKEN"
    receiver_key_id: str | None = None  # the event signing-key handle = the registered log_ingest_key_id
    receiver_executor_id: str | None = None
    receiver_org_id: str | None = None  # the heartbeat's X-Org-Id
    receiver_workspace: str = "."
    receiver_max_parallel: int = 4
    receiver_heartbeat_s: float = 30.0


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

    iplanic = data.get("iplanic")
    if isinstance(iplanic, dict):
        sync = iplanic.get("sync")
        if isinstance(sync, dict) and "enabled" in sync:
            cfg.iplanic_sync_enabled = bool(sync["enabled"])
        if iplanic.get("endpoint") is not None:
            cfg.iplanic_endpoint = str(iplanic["endpoint"])
        if iplanic.get("token_env") is not None:
            cfg.iplanic_token_env = str(iplanic["token_env"])
        if iplanic.get("max_age_s") is not None:
            cfg.iplanic_max_age_s = int(iplanic["max_age_s"])

    receiver = data.get("receiver")
    if isinstance(receiver, dict):
        if "enabled" in receiver:
            cfg.receiver_enabled = bool(receiver["enabled"])
        for str_field in ("bind", "auth_env", "key_id", "executor_id", "org_id", "workspace"):
            if receiver.get(str_field) is not None:
                setattr(cfg, f"receiver_{str_field}", str(receiver[str_field]))
        if receiver.get("port") is not None:
            cfg.receiver_port = int(receiver["port"])
        if receiver.get("max_parallel") is not None:
            cfg.receiver_max_parallel = int(receiver["max_parallel"])
        if receiver.get("heartbeat_s") is not None:
            cfg.receiver_heartbeat_s = float(receiver["heartbeat_s"])

    cfg.secrets = secrets_from_env(env=environ)
    signing_key = environ.get("IOPS_SIGNING_KEY")
    if signing_key:
        cfg.signing_key = signing_key
    return cfg
