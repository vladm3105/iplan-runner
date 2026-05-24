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

    workspace_root = Path(workspace).resolve()
    target = workspace_root / path
    # Realpath containment (symlink defense): the deepest existing ancestor must
    # resolve inside the workspace, so a symlink within allowed_roots cannot
    # redirect the write outside.
    ancestor = target
    while not ancestor.exists():
        ancestor = ancestor.parent
    resolved = ancestor.resolve()
    if resolved != workspace_root and workspace_root not in resolved.parents:
        raise PermissionError(f"sandbox denied {path}: SANDBOX.ESCAPE (realpath)")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return path
