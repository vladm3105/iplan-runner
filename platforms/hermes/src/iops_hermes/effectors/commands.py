"""Run a command inside the workspace (no shell)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def run_command(cmd: list[str], workspace: str | Path) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return {"exit_code": proc.returncode, "output": proc.stdout + proc.stderr}
