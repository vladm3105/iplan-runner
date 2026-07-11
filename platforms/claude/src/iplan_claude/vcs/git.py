"""Real git operations for landing (no remote / push)."""

from __future__ import annotations

import re
import subprocess  # nosec B404 - git landing; fixed argv, list-form, no shell
from pathlib import Path

# A git remote-helper spec `<transport>::<address>` (e.g. `ext::sh -c …`) is arbitrary
# code execution. The door's scheme allow-list is the primary gate, but this sink
# guard makes `clone()` self-protecting: it refuses the `::` helper form (and a
# leading-dash url) unconditionally, so no future caller — or the test-only scheme
# exemption — can route a remote-helper URL into git.
_REMOTE_HELPER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+.\-]*::")


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


def clone(url: str, ref: str, dest: str | Path) -> str:
    """Clone `url` into `dest` and check out `ref` (a branch, tag, or SHA); return the checked-out SHA.

    A **full** clone (no `--depth`) so an arbitrary-commit `ref` is resolvable — a shallow clone would
    lack SHAs not at a branch tip. Same fixed-argv / `check=True` / no-shell posture as `_git`; `git clone`
    is a sibling call (not `git -C`), so it is not routed through `_git`.
    """
    # B1 (PLAN-025) sink guard: refuse a git remote-helper URL (`ext::sh -c …` = RCE)
    # or a leading-dash url regardless of how we were called (the door's allow-list is
    # the primary gate; this keeps the dangerous sink safe under any future caller).
    if _REMOTE_HELPER.match(url) or url.startswith("-"):
        raise ValueError(f"unsafe clone url (remote-helper / leading-dash): {url!r}")
    # argv hardening: `--` ends option parsing so a leading-dash `url` can never be
    # read as a git switch; a trailing `--` on checkout forces `ref` to parse as a
    # rev, never a pathspec. (A leading-dash `ref` is rejected at the door — a trailing
    # `--` does not stop git from parsing it as a switch.)
    subprocess.run(  # nosec - fixed git argv, list-form, no shell
        ["git", "clone", "--no-single-branch", "--", url, str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(dest, "checkout", ref, "--")
    return head_sha(dest)


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
