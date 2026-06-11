"""Iplanic remote-executor task-payload validation (category REMOTE-001).

The payload must carry the identity + work that the run loop cannot infer; absent
fields produce findings rather than silent defaults (REMOTE_EXECUTOR_CONTRACT.md).
"""

from __future__ import annotations

from typing import Any

from ._base import Finding, finding

_REQUIRED_IDS = ("org_id", "project_id", "run_id", "step_id", "executor_id")


def validate_payload(payload: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    if any(not payload.get(k) for k in _REQUIRED_IDS):
        findings.append(finding("REMOTE.PAYLOAD_IDS_MISSING", "task payload missing a required identity field"))

    work_order = payload.get("work_order") or {}
    if not (work_order.get("todos") or []):
        findings.append(finding("REMOTE.PAYLOAD_NO_TODOS", "task payload work_order has no todos"))

    if not payload.get("context_package"):
        findings.append(finding("REMOTE.PAYLOAD_CONTEXT_MISSING", "task payload missing context_package"))

    return findings
