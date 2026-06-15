"""Authenticated ledger: HMAC-SHA256 over the canonical full event."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from ..ledger.store import verify_chain


def _canonical(event: dict[str, Any]) -> str:
    return json.dumps(
        {k: v for k, v in event.items() if k != "signature"},
        sort_keys=True,
        separators=(",", ":"),
    )


def sign_event(event: dict[str, Any], key: str) -> str:
    mac = hmac.new(key.encode(), _canonical(event).encode(), hashlib.sha256)
    return "hmac-sha256:" + mac.hexdigest()


def sign_ledger(ledger: dict[str, Any], key: str) -> dict[str, Any]:
    for event in ledger.get("execution_log", []):
        event["signature"] = sign_event(event, key)
    return ledger


def verify_ledger(ledger: dict[str, Any], key: str) -> bool:
    log = ledger.get("execution_log", [])
    if not verify_chain(log):
        return False
    for event in log:
        signature = event.get("signature")
        if signature is None or not hmac.compare_digest(signature, sign_event(event, key)):
            return False
    return True
