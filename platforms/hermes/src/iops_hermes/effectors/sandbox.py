"""Pure path-jail decision (see framework/effectors/SANDBOX_CONTRACT.md)."""

from __future__ import annotations

import posixpath
from typing import Any


def classify_path(path: str, allowed_roots: list[str]) -> dict[str, Any]:
    if posixpath.isabs(path):
        return {"allowed": False, "reason": "SANDBOX.ESCAPE"}
    normalized = posixpath.normpath(path)
    if normalized == ".." or normalized.startswith("../"):
        return {"allowed": False, "reason": "SANDBOX.ESCAPE"}
    for root in allowed_roots:
        base = posixpath.normpath(root)
        if normalized == base or normalized.startswith(base + "/"):
            return {"allowed": True, "reason": "SANDBOX.OK"}
    return {"allowed": False, "reason": "SANDBOX.OUTSIDE_ROOTS"}
