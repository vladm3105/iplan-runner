"""Ledger signing, authz, realpath sandbox hardening (Hermes)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from iops_hermes.effectors.apply import apply_write
from iops_hermes.security.authz import authorize
from iops_hermes.security.signing import sign_event, sign_ledger, verify_ledger

ROOT = Path(__file__).resolve().parents[3]
SIGNING = ROOT / "framework/conformance/signing"
AUTHZ = ROOT / "framework/conformance/authz"


@pytest.mark.parametrize("case", sorted(p.name for p in SIGNING.iterdir()))
def test_sign_event_matches_vectors(case: str) -> None:
    inp = yaml.safe_load((SIGNING / case / "input.yaml").read_text())
    expect = yaml.safe_load((SIGNING / case / "expect.yaml").read_text())
    assert sign_event(inp["event"], inp["key"]) == expect["signature"]


@pytest.mark.parametrize("case", sorted(p.name for p in AUTHZ.iterdir()))
def test_authorize_matches_vectors(case: str) -> None:
    inp = yaml.safe_load((AUTHZ / case / "input.yaml").read_text())
    expect = yaml.safe_load((AUTHZ / case / "expect.yaml").read_text())
    assert authorize(inp["actor"], inp["action"]) == expect


def test_sign_verify_roundtrip_and_tamper() -> None:
    from iops_hermes.ledger.store import append_event

    ledger: dict = {"execution_log": []}
    append_event(ledger, {"event_type": "task_started", "subject_id": "T1", "at": "t0",
                          "touched_paths": [], "client_id": "c", "project_id": "p"})
    append_event(ledger, {"event_type": "file_edited", "subject_id": "T1", "at": "t1",
                          "touched_paths": ["src/a.py"], "client_id": "c", "project_id": "p"})

    sign_ledger(ledger, "k")
    assert verify_ledger(ledger, "k") is True
    assert verify_ledger(ledger, "wrong-key") is False

    # tamper a non-hashed field -> signature (over full event) no longer matches
    ledger["execution_log"][1]["touched_paths"] = ["src/evil.py"]
    assert verify_ledger(ledger, "k") is False

    # missing signature -> invalid
    sign_ledger(ledger, "k")
    del ledger["execution_log"][0]["signature"]
    assert verify_ledger(ledger, "k") is False


def test_realpath_blocks_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_target"
    outside.mkdir(exist_ok=True)
    ws = tmp_path / "ws"
    ws.mkdir()
    os.symlink(outside, ws / "src")  # src/ is a symlink escaping the workspace
    with pytest.raises(PermissionError):
        apply_write("src/a.py", "x", ws, ["src/"])
