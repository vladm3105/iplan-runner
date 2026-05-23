"""Chain-ledger validation (category IPLAN-008)."""
from __future__ import annotations

from typing import Any

from ._base import Finding, finding


def _leases_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        str(a.get("acquired_at")) < str(b.get("expires_at"))
        and str(b.get("acquired_at")) < str(a.get("expires_at"))
    )


def validate_chain(document: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    chain = document.get("iplan_chain", [])
    order = {c.get("iplan_id"): c.get("order") for c in chain}
    reconciled = {c.get("iplan_id"): c.get("reconciled") for c in chain}

    order_invalid = False
    upstream_unreconciled = False
    for node in chain:
        for dep in node.get("depends_on", []):
            dep_order = order.get(dep)
            if (
                dep_order is not None
                and node.get("order") is not None
                and node["order"] <= dep_order
            ):
                order_invalid = True
            if dep in reconciled and not reconciled[dep]:
                upstream_unreconciled = True

    if order_invalid:
        findings.append(
            finding("CHAIN.ORDER_INVALID", "an IPLAN is ordered at/before a dependency")
        )
    if upstream_unreconciled:
        findings.append(
            finding(
                "CHAIN.UPSTREAM_UNRECONCILED",
                "an IPLAN depends on an unreconciled upstream",
            )
        )

    by_resource: dict[str, list[dict[str, Any]]] = {}
    for lease in document.get("cross_plan_leases", []):
        if lease.get("released_at") is None:
            by_resource.setdefault(str(lease.get("resource")), []).append(lease)
    for resource, leases in by_resource.items():
        overlap = any(
            _leases_overlap(leases[i], leases[j])
            for i in range(len(leases))
            for j in range(i + 1, len(leases))
        )
        if overlap:
            findings.append(
                finding(
                    "CHAIN.LEASE_OVERLAP",
                    f"overlapping unreleased leases on resource {resource}",
                )
            )

    return findings
