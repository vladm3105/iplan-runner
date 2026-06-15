"""Read-only reader for a source SDD IPLAN reference."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


def read_iplan_ref(path: str | Path) -> dict[str, Any]:
    """Return ``{id, version, last_updated, checksum}`` for an IPLAN file.

    ``checksum`` is ``"sha256:" + sha256(file_bytes)``. Tolerant of missing
    document_control fields so it works on any IPLAN-shaped YAML.
    """
    raw = Path(path).read_bytes()
    checksum = "sha256:" + hashlib.sha256(raw).hexdigest()
    parsed: Any = yaml.safe_load(raw)
    document = parsed if isinstance(parsed, dict) else {}
    control = document.get("document_control", {})
    return {
        "id": control.get("iplan_id") or control.get("id"),
        "version": control.get("version"),
        "last_updated": control.get("last_updated"),
        "checksum": checksum,
    }
