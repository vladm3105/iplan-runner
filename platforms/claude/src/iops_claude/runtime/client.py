"""Pluggable host-runtime transport. Stub is offline/deterministic; the real
Claude Code hook adapter is integration-only (environment-specific)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class RuntimeResult:
    success: bool
    changed_files: list[str] = field(default_factory=list)
    output: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class RuntimeClient(Protocol):
    def run_task(self, task: dict[str, Any], workspace: str | Path) -> RuntimeResult: ...


class StubRuntimeClient:
    """Returns a canned runtime result (offline tests / scenarios)."""

    def __init__(self, result: RuntimeResult | None = None) -> None:
        self._result = result or RuntimeResult(success=True)

    def run_task(self, task: dict[str, Any], workspace: str | Path) -> RuntimeResult:
        return self._result
