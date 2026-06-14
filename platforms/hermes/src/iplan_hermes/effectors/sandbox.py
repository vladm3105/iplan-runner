"""Pure path-jail decision (see framework/effectors/SANDBOX_CONTRACT.md)."""

from __future__ import annotations

import posixpath
from collections.abc import Sequence
from typing import Any


def classify_path(path: str, allowed_roots: list[str], forbidden_paths: Sequence[str] = ()) -> dict[str, Any]:
    if posixpath.isabs(path):
        return {"allowed": False, "reason": "SANDBOX.ESCAPE"}
    normalized = posixpath.normpath(path)
    if normalized == ".." or normalized.startswith("../"):
        return {"allowed": False, "reason": "SANDBOX.ESCAPE"}
    for root in allowed_roots:
        base = posixpath.normpath(root)
        if normalized == base or normalized.startswith(base + "/"):
            # Forbidden check, after the positive jail: ESCAPE/OUTSIDE_ROOTS win.
            for forbidden in forbidden_paths:
                fb = posixpath.normpath(forbidden)
                if normalized == fb or normalized.startswith(fb + "/"):
                    return {"allowed": False, "reason": "SANDBOX.FORBIDDEN"}
            return {"allowed": True, "reason": "SANDBOX.OK"}
    return {"allowed": False, "reason": "SANDBOX.OUTSIDE_ROOTS"}
