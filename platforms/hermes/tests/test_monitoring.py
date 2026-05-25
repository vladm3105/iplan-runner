"""Monitoring runtime: alerts, issue record, probe server, self-telemetry (Hermes)."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest
import yaml
from iops_hermes.monitoring.alerts import build_issue, evaluate_alerts
from iops_hermes.monitoring.probes import probe_server
from iops_hermes.monitoring.telemetry import emit_run_telemetry

ROOT = Path(__file__).resolve().parents[3]
ALERT = ROOT / "framework/conformance/alert"


@pytest.mark.parametrize("case", sorted(p.name for p in ALERT.iterdir()))
def test_evaluate_alerts_matches_vectors(case: str) -> None:
    inp = yaml.safe_load((ALERT / case / "input.yaml").read_text())
    expect = yaml.safe_load((ALERT / case / "expect.yaml").read_text())
    assert expect == {"alerts": evaluate_alerts(inp["manifest"], inp["samples"])}


def test_build_issue_binds_identity() -> None:
    manifest = {"monitor_control": {"source_iplan": "IPLAN-001", "source_ledger": "LEDGER-IPLAN-001"}}
    alert = {"alert_id": "ALERT-001", "slo_ref": "SLO-001", "severity": "error", "escalation_owner": "operator"}
    issue = build_issue(alert, manifest)
    assert issue["source_iplan"] == "IPLAN-001"
    assert issue["source_ledger"] == "LEDGER-IPLAN-001"
    assert issue["severity"] == "error"


def test_probe_server_serves_health() -> None:
    manifest = {"probes": {"health": "/healthz", "readiness": "/readyz", "startup": "/startupz"}}
    server = probe_server(manifest, lambda: {"status": "ok"})
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        for path in ("/healthz", "/readyz", "/startupz"):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as resp:
                assert resp.status == 200
                assert json.loads(resp.read())["status"] == "ok"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_provider_record_does_not_raise() -> None:
    # works for the no-op default (offline) and the real OTel provider if installed
    from iops_hermes.monitoring.otel import get_provider

    provider = get_provider("iops-hermes")
    provider.record_metric("m", 1.0)
    provider.log("ev", "INFO", "body")


def test_emit_run_telemetry() -> None:
    recorded: list[tuple[str, float]] = []

    class _Provider:
        def start_span(self, name: str, attributes: dict) -> None: ...
        def record_metric(self, name: str, value: float) -> None:
            recorded.append((name, value))

        def log(self, name: str, severity: str, body: str) -> None: ...

    ledger = {
        "task_ledger": [
            {"task_id": "T1", "status": "completed"},
            {"task_id": "T2", "status": "blocked"},
        ]
    }
    emit_run_telemetry(_Provider(), ledger)
    metrics = dict(recorded)
    assert metrics["iplan.tasks.completed"] == 1
    assert metrics["iplan.tasks.blocked"] == 1
