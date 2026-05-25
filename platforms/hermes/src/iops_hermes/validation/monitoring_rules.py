"""Monitoring-manifest validation (category MON-001)."""

from __future__ import annotations

from typing import Any

from ._base import Finding, finding


def validate_monitoring(document: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    control = document.get("monitor_control", {})
    if not (control.get("source_iplan") and control.get("source_ledger")):
        findings.append(
            finding(
                "MON.SOURCE_BINDING_MISSING",
                "monitor_control is missing source_iplan or source_ledger",
            )
        )

    metrics = {m.get("name") for m in document.get("signals", {}).get("otel", {}).get("metrics", [])}
    missing_target = False
    unresolved_ref = False
    for slo in document.get("slos", []):
        if slo.get("objective") is None:
            missing_target = True
        ref = slo.get("signal_ref")
        if ref is not None and ref not in metrics:
            unresolved_ref = True
    if missing_target:
        findings.append(finding("MON.SLO_MISSING_TARGET", "an SLO has no objective"))
    if unresolved_ref:
        findings.append(
            finding(
                "MON.SIGNAL_REF_UNRESOLVED",
                "an SLO signal_ref does not resolve to a declared metric",
            )
        )

    probes = document.get("probes", {})
    if not (probes.get("health") and probes.get("readiness") and probes.get("startup")):
        findings.append(finding("MON.PROBE_MISSING", "a health/readiness/startup probe is missing"))

    return findings
