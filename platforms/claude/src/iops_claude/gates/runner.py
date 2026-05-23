"""Evaluate a verification-gate document against a ledger.

Each GATE-LEDGER-NNN rule references the validator rule IDs it depends on; the
gate fails if any referenced rule fired during ledger validation.
"""
from __future__ import annotations

from typing import Any

from ..validation.ledger_rules import validate_ledger


def run_gate(ledger: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    fired = {f.rule_id for f in validate_ledger(ledger)}

    rule_results: list[dict[str, Any]] = []
    overall = "passed"
    for rule in gate.get("gate_rules", []):
        referenced = set(rule.get("rule_ids", []))
        violations = sorted(fired & referenced)
        passed = not violations
        if not passed:
            overall = "failed"
        rule_results.append(
            {
                "id": rule.get("id"),
                "status": "passed" if passed else "failed",
                "violations": violations,
            }
        )

    return {"status": overall, "rules": rule_results}
