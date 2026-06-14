"""Lease lifecycle decisions (see framework/execution/LEASE_MODEL.md)."""

from __future__ import annotations

from typing import Any


def lease_state(lease: dict[str, Any], now: str) -> str:
    if lease.get("released_at"):
        return "released"
    expires = lease.get("expires_at")
    if expires and now > str(expires):
        return "expired"
    return "active"


def can_acquire(existing: list[dict[str, Any]], task_id: str, now: str) -> bool:
    return not any(lease.get("task_id") == task_id and lease_state(lease, now) == "active" for lease in existing)


def renew(lease: dict[str, Any], new_expiry: str) -> dict[str, Any]:
    lease["expires_at"] = new_expiry
    return lease
