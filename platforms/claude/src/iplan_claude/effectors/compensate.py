"""Undo partial writes during saga compensation (workspace-contained)."""

from __future__ import annotations

from pathlib import Path


def undo_writes(touched_paths: list[str], workspace: str | Path) -> list[str]:
    root = Path(workspace).resolve()
    removed: list[str] = []
    for path in touched_paths:
        target = (root / path).resolve()
        if target.is_relative_to(root) and target.is_file():
            target.unlink()
            removed.append(path)
    return removed
