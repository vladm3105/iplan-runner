"""Deterministic secret redaction."""
from __future__ import annotations


def redact(value: str, secrets: list[str]) -> str:
    result = value
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        result = result.replace(secret, "***")
    return result
