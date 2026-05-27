"""Real git operations for landing (no remote / push)."""

from __future__ import annotations

import subprocess  # nosec B404 - git landing; fixed argv, list-form, no shell
from pathlib import Path


def _git(workspace: str | Path, *args: str) -> str:
    proc = subprocess.run(  # nosec - fixed git argv, list-form, no shell
        ["git", "-C", str(workspace), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def has_changes(workspace: str | Path) -> bool:
    return bool(_git(workspace, "status", "--porcelain"))


def head_sha(workspace: str | Path) -> str:
    return _git(workspace, "rev-parse", "HEAD")


def current_branch(workspace: str | Path) -> str:
    return _git(workspace, "rev-parse", "--abbrev-ref", "HEAD")


def commit_all(
    workspace: str | Path,
    branch: str,
    message: str,
    *,
    author_name: str = "iops-engine",
    author_email: str = "iops@local",
) -> str:
    _git(workspace, "checkout", "-B", branch)
    _git(workspace, "add", "-A")
    # Self-contained commit: explicit identity, and no signing — the engine must
    # not depend on (or be broken by) the operator's ambient git/signing config.
    _git(
        workspace,
        "-c",
        f"user.name={author_name}",
        "-c",
        f"user.email={author_email}",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        message,
    )
    return head_sha(workspace)
