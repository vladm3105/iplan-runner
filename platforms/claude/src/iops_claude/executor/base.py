"""Executor interface + value types (see framework/engines/EXECUTOR-CONTRACT.md)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass
class ExecutionContext:
    task: dict[str, Any]
    isolation_scope: dict[str, Any]
    clock: Callable[[], str]
    ids: Callable[[str], str]


@dataclass
class ExecutorResult:
    outcome: str  # "success" | "failure"
    touched_paths: list[str] = field(default_factory=list)
    evidence: dict[str, Any] | None = None
    reason: str | None = None
    retriable: bool = False


class Executor(Protocol):
    def execute(self, task: dict[str, Any], ctx: ExecutionContext) -> ExecutorResult: ...

    def compensate(self, touched_paths: list[str]) -> None: ...


class IdSource:
    """Deterministic per-prefix id generator: ids("L") -> "L1", "L2", ..."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def __call__(self, prefix: str) -> str:
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}{self._counters[prefix]}"
