"""SLO-breach-driven alert evaluation + issue record (see MONITORING_RUNTIME.md)."""

from __future__ import annotations

from typing import Any

from .slo import evaluate_slos


def evaluate_alerts(manifest: dict[str, Any], samples: dict[str, float]) -> list[dict[str, Any]]:
    by_id = {r["id"]: r for r in evaluate_slos(manifest, samples)}
    alerts: list[dict[str, Any]] = []
    for rule in manifest.get("alert_rules", []):
        slo = by_id.get(rule.get("slo_ref"))
        if slo is None:
            continue
        if slo["met"] is False:
            alerts.append(
                {
                    "alert_id": rule.get("id"),
                    "slo_ref": rule.get("slo_ref"),
                    "severity": rule.get("severity"),
                    "escalation_owner": rule.get("escalation_owner"),
                }
            )
    return alerts


def build_issue(alert: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    control = manifest.get("monitor_control", {})
    return {
        "title": f"SLO breach: {alert.get('slo_ref')} ({control.get('source_iplan')})",
        "body": (
            f"Alert {alert.get('alert_id')} fired for SLO {alert.get('slo_ref')} "
            f"on ledger {control.get('source_ledger')}."
        ),
        "source_iplan": control.get("source_iplan"),
        "source_ledger": control.get("source_ledger"),
        "severity": alert.get("severity"),
        "escalation_owner": alert.get("escalation_owner"),
    }
