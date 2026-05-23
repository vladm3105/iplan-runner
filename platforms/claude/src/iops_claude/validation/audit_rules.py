"""Audit-report validation (category IPLAN-009)."""
from __future__ import annotations

from typing import Any

from ._base import Finding, finding


def validate_audit(document: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    scope = document.get("version_scope", {})
    baseline = scope.get("baseline", {})
    comparison = scope.get("comparison", {})

    if baseline.get("source_iplan") != comparison.get("source_iplan"):
        findings.append(
            finding(
                "AUDIT.IDENTITY_MISMATCH",
                "baseline and comparison reference different source IPLANs",
            )
        )

    baseline_ok = baseline.get("source_iplan_version") and baseline.get(
        "source_iplan_checksum"
    )
    comparison_ok = comparison.get("source_iplan_version") and comparison.get(
        "source_iplan_checksum"
    )

    if not (baseline_ok and comparison_ok):
        findings.append(
            finding(
                "AUDIT.VERSION_MISSING",
                "baseline or comparison is missing version/checksum",
            )
        )
    elif (
        baseline["source_iplan_version"] == comparison["source_iplan_version"]
        and baseline["source_iplan_checksum"] != comparison["source_iplan_checksum"]
    ):
        findings.append(
            finding(
                "AUDIT.VERSION_INCONSISTENT",
                "same version but differing checksum",
            )
        )

    return findings
