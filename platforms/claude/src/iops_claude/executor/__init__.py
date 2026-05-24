"""Pluggable executor seam (D-0013)."""

from .base import Executor, ExecutionContext, ExecutorResult, IdSource
from .mock import MockExecutor

__all__ = ["Executor", "ExecutionContext", "ExecutorResult", "IdSource", "MockExecutor"]
