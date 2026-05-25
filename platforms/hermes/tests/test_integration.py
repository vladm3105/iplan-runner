"""End-to-end ledger lifecycle for the Hermes engine."""

from __future__ import annotations

from pathlib import Path

import yaml
from iops_hermes import HermesEngine
from iops_hermes.audit.report import build_audit_report
from iops_hermes.iplan import read_iplan_ref
from iops_hermes.ledger.store import append_event, verify_chain
from iops_hermes.monitoring.slo import evaluate_slos

ROOT = Path(__file__).resolve().parents[3]
VECTORS = ROOT / "framework" / "conformance" / "vectors"


def _load(rel: str) -> dict:
    return yaml.safe_load((VECTORS / rel).read_text())


def test_source_iplan_binding(tmp_path: Path) -> None:
    iplan = tmp_path / "IPLAN-001.yaml"
    iplan.write_text("document_control:\n  iplan_id: IPLAN-001\n  version: 1.2.0\n")
    ref = read_iplan_ref(iplan)
    assert ref["id"] == "IPLAN-001"
    assert ref["version"] == "1.2.0"
    assert ref["checksum"].startswith("sha256:")


def test_ledger_lifecycle_and_gate() -> None:
    engine = HermesEngine()
    ledger = _load("ledger/valid_completed.yaml")

    assert verify_chain(ledger["execution_log"]) is True
    append_event(
        ledger,
        {
            "event_type": "task_completed",
            "subject_id": "T1",
            "at": "2026-05-23T10:45:00Z",
            "touched_paths": ["src/foo.py"],
            "client_id": "client-a",
            "project_id": "project-x",
        },
    )
    assert verify_chain(ledger["execution_log"]) is True
    assert engine.validate(ledger)["status"] == "pass"

    gate = yaml.safe_load((ROOT / "framework/execution/IPLAN-VERIFY-TEMPLATE.yaml").read_text())
    assert engine.run_gate(ledger, gate)["status"] == "passed"


def test_chain_reconcile_and_audit() -> None:
    engine = HermesEngine()
    assert engine.validate(_load("chain/valid_chain.yaml"))["status"] == "pass"
    assert engine.validate(_load("chain/order_invalid.yaml"))["status"] == "fail"

    baseline = _load("ledger/valid_completed.yaml")
    comparison = _load("ledger/valid_completed.yaml")
    report = build_audit_report(baseline, comparison)
    assert engine.validate(report)["status"] == "pass"


def test_slo_evaluation() -> None:
    manifest = _load("monitoring/valid_manifest.yaml")
    results = evaluate_slos(manifest, {"availability_ratio": 99.95})
    assert results[0]["met"] is True
