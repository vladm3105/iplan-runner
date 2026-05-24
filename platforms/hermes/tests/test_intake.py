"""Intake reader + handover builder (beyond vector replay)."""
from __future__ import annotations

from pathlib import Path

from iops_hermes import HermesEngine
from iops_hermes.handover.receipt import build_handover_receipt
from iops_hermes.intake.reader import ingest_iplan

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ROOT / "framework" / "conformance" / "intake_samples"


def test_ingest_minimal_validates_pass() -> None:
    engine = HermesEngine()
    manifest = engine.ingest_iplan(SAMPLES / "minimal" / "iplan.yaml")
    assert manifest["metadata"]["document_type"] == "iplan-intake"
    assert manifest["intake_control"]["source_iplan"] == "IPLAN-001"
    assert manifest["intake_control"]["source_iplan_checksum"].startswith("sha256:")
    assert manifest["task_graph"][0]["task_id"] == "T1"
    assert engine.validate(manifest)["status"] == "pass"


def test_ingest_with_deps_validates_pass() -> None:
    manifest = ingest_iplan(SAMPLES / "with_deps" / "iplan.yaml")
    assert [t["task_id"] for t in manifest["task_graph"]] == ["T1", "T2"]
    assert HermesEngine().validate(manifest)["status"] == "pass"


def test_handover_builder_is_deterministic() -> None:
    ledger = {
        "ledger_control": {
            "ledger_id": "LEDGER-IPLAN-001",
            "source_iplan": "IPLAN-001",
            "source_iplan_version": "1.2.0",
        },
        "task_ledger": [{"task_id": "T1", "status": "completed"}],
        "reconciliation": {"allowed": True},
    }
    receipt = build_handover_receipt(
        ledger, {"status": "passed"}, clock=lambda: "2026-05-24T00:00:00Z"
    )
    assert receipt["handover_control"]["receipt_id"] == "RECEIPT-LEDGER-IPLAN-001"
    assert receipt["handover_control"]["created_at"] == "2026-05-24T00:00:00Z"
    assert receipt["result"]["status"] == "completed"
    assert HermesEngine().validate(receipt)["status"] == "pass"
