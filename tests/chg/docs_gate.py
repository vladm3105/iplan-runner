#!/usr/bin/env python3
"""Diff-aware documentation gate.

A PR that changes the framework contract or an engine's shipped code must update
`CHANGELOG.md` in the same PR (an `[Unreleased]` entry, or a release header for
a version cut). README / ROADMAP / HANDOFF / TODO / `docs/**` are judgment calls
per PR — encoded as guidelines, not gated here.

Escape hatch: include the literal marker `[no-changelog]` anywhere in any commit
message in the PR when the change is genuinely not user-facing (e.g. an
internal refactor with no behavior change, a pure test addition, a CI tweak).

Run in CI on `pull_request`:

    GATE_BASE=origin/main python tests/chg/docs_gate.py
"""

from __future__ import annotations

import os
import re
import subprocess  # nosec B404 - reads git diff/log only, list-form, no shell
import sys

CHANGELOG = "CHANGELOG.md"
ESCAPE_MARKER = "[no-changelog]"

# Trigger paths: a touch to any of these means CHANGELOG.md must move too,
# unless the escape marker is present. Tests and docs are deliberately not
# triggers; pure test/doc PRs don't require a CHANGELOG entry.
TRIGGERS = [
    re.compile(r"^framework/"),
    re.compile(r"^platforms/[^/]+/src/"),
    re.compile(r"^platforms/[^/]+/pyproject\.toml$"),
    re.compile(r"^platforms/[^/]+/FRAMEWORK_SPEC_VERSION$"),
]


def _git(*args: str) -> str:
    return subprocess.run(  # nosec - fixed git argv, list-form, no shell
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def main() -> int:
    base = os.environ.get("GATE_BASE", "origin/main")
    changed = [line for line in _git("diff", "--name-only", f"{base}...HEAD").splitlines() if line]
    if not any(pat.match(path) for pat in TRIGGERS for path in changed):
        print(f"docs-gate: no triggering paths in {base}...HEAD; skipping.")
        return 0

    if CHANGELOG in changed:
        print(f"docs-gate: {CHANGELOG} updated; ok.")
        return 0

    messages = _git("log", f"{base}..HEAD", "--format=%B")
    if ESCAPE_MARKER in messages:
        print(f"docs-gate: '{ESCAPE_MARKER}' escape present in commit messages; ok.")
        return 0

    print(
        f"docs-gate: this PR changes framework/ or an engine's src/pyproject/version but does NOT update {CHANGELOG}.",
        file=sys.stderr,
    )
    print(
        f"  Update {CHANGELOG} (an '[Unreleased]' entry is enough), or include "
        f"'{ESCAPE_MARKER}' in a commit message if the change is genuinely "
        f"not user-facing.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
