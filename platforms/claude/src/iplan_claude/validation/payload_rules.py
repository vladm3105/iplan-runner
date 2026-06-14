"""Iplanic remote-executor task-payload validation (category REMOTE-001).

The payload must carry the identity + work that the run loop cannot infer; absent
fields produce findings rather than silent defaults (REMOTE_EXECUTOR_CONTRACT.md).
"""

from __future__ import annotations

import re
from typing import Any

from ._base import Finding, finding

_REQUIRED_IDS = ("org_id", "project_id", "run_id", "step_id", "executor_id")

# Iplanic executor_id hash form (Iplanic §2.1 / D-0031): exec:<base32(sha256(...))>.
_EXECUTOR_ID = re.compile(r"^exec:[a-z2-7]{16,}$")


def validate_payload(payload: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    if any(not payload.get(k) for k in _REQUIRED_IDS):
        findings.append(finding("REMOTE.PAYLOAD_IDS_MISSING", "task payload missing a required identity field"))

    executor_id = payload.get("executor_id")
    if executor_id and not (isinstance(executor_id, str) and _EXECUTOR_ID.match(executor_id)):
        findings.append(
            finding("REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT", "executor_id is not the canonical exec: hash form")
        )

    work_order = payload.get("work_order") or {}
    if not (work_order.get("todos") or []):
        findings.append(finding("REMOTE.PAYLOAD_NO_TODOS", "task payload work_order has no todos"))

    if not payload.get("context_package"):
        findings.append(finding("REMOTE.PAYLOAD_CONTEXT_MISSING", "task payload missing context_package"))

    return findings
