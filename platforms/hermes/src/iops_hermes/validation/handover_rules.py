"""Handover receipt validation (category HANDOVER-001).

Internal-consistency only — does not read the referenced ledger.
"""

from __future__ import annotations

from typing import Any

from ._base import Finding, finding

VALID_STATUS = {"completed", "aborted"}


def validate_handover(document: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    control = document.get("handover_control", {})
    if not (control.get("source_iplan") and control.get("ledger_ref")):
        findings.append(finding("HANDOVER.SOURCE_MISSING", "source_iplan or ledger_ref missing"))

    result = document.get("result", {})
    status = result.get("status")
    if status not in VALID_STATUS:
        findings.append(finding("HANDOVER.STATUS_INVALID", "result.status is not completed/aborted"))

    if status == "completed":
        if control.get("gate_status") != "passed":
            findings.append(finding("HANDOVER.GATE_NOT_PASSED", "completed but gate not passed"))
        if not result.get("reconciled"):
            findings.append(finding("HANDOVER.NOT_RECONCILED", "completed but not reconciled"))

    return findings
