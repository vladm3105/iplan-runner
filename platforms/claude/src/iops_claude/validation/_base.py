"""Findings + severities for the Hermes validators.

The severity map mirrors framework/conformance/rule-ids.yaml. Strict isolation
(D-0011) means this engine carries its own copy; conformance asserts it matches
the catalog.
"""
from __future__ import annotations

from dataclasses import dataclass

SEVERITY: dict[str, str] = {
    "LEDGER.SOURCE_VERSION_MISSING": "error",
    "LEDGER.EVIDENCE_REQUIRED": "error",
    "LEDGER.ACCEPTANCE_WEAK": "error",
    "LEDGER.BLOCKED_WITHOUT_OWNER": "error",
    "LEDGER.LEASE_OVERLAP": "error",
    "LEDGER.RECONCILE_INCONSISTENT": "error",
    "ISOLATION.SCOPE_MISSING": "error",
    "ISOLATION.PATH_OUTSIDE_ROOTS": "error",
    "ISOLATION.EVENT_SCOPE_MISMATCH": "error",
    "HASHCHAIN.BROKEN": "error",
    "CHAIN.ORDER_INVALID": "error",
    "CHAIN.UPSTREAM_UNRECONCILED": "error",
    "CHAIN.LEASE_OVERLAP": "error",
    "AUDIT.IDENTITY_MISMATCH": "error",
    "AUDIT.VERSION_MISSING": "error",
    "AUDIT.VERSION_INCONSISTENT": "error",
    "MON.SOURCE_BINDING_MISSING": "error",
    "MON.SLO_MISSING_TARGET": "error",
    "MON.SIGNAL_REF_UNRESOLVED": "error",
    "MON.PROBE_MISSING": "warning",
}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str


def finding(rule_id: str, message: str) -> Finding:
    return Finding(rule_id, SEVERITY[rule_id], message)


def status_of(findings: list[Finding]) -> str:
    severities = {f.severity for f in findings}
    if "error" in severities:
        return "fail"
    if "warning" in severities:
        return "warn"
    return "pass"
