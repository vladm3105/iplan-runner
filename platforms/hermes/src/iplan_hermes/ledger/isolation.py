"""Isolation-scope helpers."""

from __future__ import annotations

from typing import Any


def in_scope(path: str, allowed_roots: list[str]) -> bool:
    return any(path.startswith(root) for root in allowed_roots)


def event_in_scope(event: dict[str, Any], client_id: str, project_id: str) -> bool:
    return event.get("client_id") == client_id and event.get("project_id") == project_id
