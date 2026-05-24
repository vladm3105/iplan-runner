"""Apply a file write through the sandbox (raises before any effect if denied)."""
from __future__ import annotations

from pathlib import Path

from .sandbox import classify_path


def apply_write(
    path: str, content: str, workspace: str | Path, allowed_roots: list[str]
) -> str:
    decision = classify_path(path, allowed_roots)
    if not decision["allowed"]:
        raise PermissionError(f"sandbox denied {path}: {decision['reason']}")
    target = Path(workspace) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return path
