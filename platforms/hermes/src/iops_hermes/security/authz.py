"""Role-based authorization (L2; see framework/security/SECURITY_MODEL.md)."""
from __future__ import annotations

from typing import Any

_ROLE_ACTIONS: dict[str, set[str]] = {
    "agent": {"run", "record", "edit"},
    "operator": {"run", "record", "edit", "land", "approve", "override"},
}


def authorize(actor: dict[str, Any], action: str) -> dict[str, Any]:
    role = actor.get("role")
    if role not in _ROLE_ACTIONS:
        return {"allowed": False, "reason": "AUTHZ.UNKNOWN_ROLE"}
    if action in _ROLE_ACTIONS[role]:
        return {"allowed": True, "reason": "AUTHZ.OK"}
    return {"allowed": False, "reason": "AUTHZ.ROLE_FORBIDDEN"}
