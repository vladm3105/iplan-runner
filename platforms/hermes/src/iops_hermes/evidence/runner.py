"""Run a task's acceptance checks, capturing redacted evidence."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..effectors.commands import run_command
from ..redaction import redact


def run_checks(
    checks: list[dict[str, Any]],
    workspace: str | Path,
    secrets: list[str] | None = None,
) -> dict[str, Any]:
    secret_list = secrets or []
    results: list[dict[str, Any]] = []
    passed = True
    for check in checks:
        outcome = run_command(check["command"], workspace)
        if outcome["exit_code"] != 0:
            passed = False
        results.append(
            {
                "name": check.get("name"),
                "exit_code": outcome["exit_code"],
                "output": redact(outcome["output"], secret_list),
            }
        )
    return {"passed": passed, "results": results}
