"""Iplanic remote-executor: payload intake, event projection, forbidden path."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import yaml
from iplan_hermes.effectors.sandbox import classify_path
from iplan_hermes.intake.payload import ingest_task_payload
from iplan_hermes.ledger.events import to_execution_events
from iplan_hermes.validation.payload_rules import validate_payload

REMOTE = Path(__file__).resolve().parents[3] / "framework" / "conformance" / "remote"


def _ids() -> Callable[[str], str]:
    counters: dict[str, int] = {}

    def make(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}-{counters[prefix]:03d}"

    return make


def test_payload_intake_maps_to_manifest() -> None:
    manifest = ingest_task_payload(str(REMOTE / "accept" / "payload.yaml"))
    assert manifest["intake_control"]["source_iplan"] == "IPLAN-01"
    assert manifest["intake_control"]["approved"] is True
    assert manifest["isolation_scope"]["client_id"] == "org-a"
    assert manifest["isolation_scope"]["forbidden_paths"] == [".git", "secrets"]
    assert manifest["remote_execution"]["executor_id"] == "exec:iopsremote2zqf7kx3a"
    assert len(manifest["task_graph"]) == 2


def test_event_projection_drops_compensation_and_derives_test() -> None:
    ledger = yaml.safe_load((REMOTE / "accept" / "ledger.yaml").read_text())
    payload = yaml.safe_load((REMOTE / "accept" / "payload.yaml").read_text())
    events = to_execution_events(ledger, payload, key=b"k", key_id="key-1", ids=_ids())
    assert [e["event_type"] for e in events] == [
        "task.started",
        "file.changed",
        "task.completed",
        "test.passed",
        "artifact.created",
    ]
    assert all(e["executor_id"] == "exec:iopsremote2zqf7kx3a" for e in events)
    assert all(set(e["signature"]) == {"key_id", "algorithm", "value"} for e in events)


def test_payload_validation_flags_missing_fields() -> None:
    payload = yaml.safe_load((REMOTE / "reject_context" / "payload.yaml").read_text())
    rule_ids = sorted(f.rule_id for f in validate_payload(payload))
    assert rule_ids == [
        "REMOTE.PAYLOAD_CONTEXT_MISSING",
        "REMOTE.PAYLOAD_IDS_MISSING",
        "REMOTE.PAYLOAD_NO_TODOS",
    ]


def test_classify_path_forbidden_precedence() -> None:
    assert classify_path("src/secrets/k", ["src/"], ["src/secrets"]) == {
        "allowed": False,
        "reason": "SANDBOX.FORBIDDEN",
    }
    # ESCAPE / OUTSIDE_ROOTS still win over FORBIDDEN.
    assert classify_path("/etc/x", ["src/"], ["src/secrets"])["reason"] == "SANDBOX.ESCAPE"
    assert classify_path("other/x", ["src/"], ["src/secrets"])["reason"] == "SANDBOX.OUTSIDE_ROOTS"
    assert classify_path("src/ok", ["src/"], ["src/secrets"]) == {"allowed": True, "reason": "SANDBOX.OK"}
