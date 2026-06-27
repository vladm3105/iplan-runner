"""Non-gated unit coverage for the PLAN-021 receiver primitives (runs in CI).

The full wire (HTTP → run → events) is the gated `test_task_receiver.py`; this
file covers the deterministic, socket-free pieces: the `(run_id, task_id)` accept
store (incl. the concurrency invariant), the dispatched-payload adapter + dict
intake, and bearer verification.
"""

from __future__ import annotations

import threading
from pathlib import Path

from iplan_hermes.intake.payload import adapt_dispatched_task, ingest_task_payload_dict
from iplan_hermes.receiver.auth import verify_bearer
from iplan_hermes.relay import store


def test_accept_then_claim_lifecycle(tmp_path: Path) -> None:
    d = str(tmp_path)
    assert store.accept_task(d, "R1", "T1") == "accept"  # fresh
    assert store.accept_task(d, "R1", "T1") == "accept"  # bare-accepted is re-runnable
    assert store.claim_task(d, "R1", "T1") is True  # accepted -> running
    assert store.claim_task(d, "R1", "T1") is False  # already running
    assert store.accept_task(d, "R1", "T1") == "replay"  # running short-circuits
    assert store.task_status(d, "R1", "T1") == "running"
    store.settle_task(d, "R1", "T1", ok=True)
    assert store.task_status(d, "R1", "T1") == "done"
    assert store.accept_task(d, "R1", "T1") == "replay"  # terminal short-circuits


def test_distinct_keys_are_independent(tmp_path: Path) -> None:
    d = str(tmp_path)
    assert store.accept_task(d, "R1", "T1") == "accept"
    assert store.accept_task(d, "R1", "T2") == "accept"  # task_id == step_id recurs; run_id differs across members
    assert store.accept_task(d, "R2", "T1") == "accept"


def test_concurrent_accept_claim_runs_once(tmp_path: Path) -> None:
    d = str(tmp_path)
    claims: list[int] = []

    def worker() -> None:
        if store.accept_task(d, "R", "T") == "accept" and store.claim_task(d, "R", "T"):
            claims.append(1)

    threads = [threading.Thread(target=worker) for _ in range(24)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(claims) == 1  # exactly one caller wins the run despite many concurrent acceptors


def test_adapt_rewrites_nested_repository_object() -> None:
    payload = {
        "run_id": "R",
        "task_id": "T",
        "context_package": {
            "repository": {"url": "https://x/r.git", "default_branch": "main", "base_ref": "abc"},
            "forbidden_paths": [".git"],
        },
    }
    adapted = adapt_dispatched_task(payload, workspace="/ws")
    assert adapted["context_package"]["repository"] == "/ws"
    assert adapted["context_package"]["forbidden_paths"] == [".git"]
    # input is not mutated
    assert isinstance(payload["context_package"]["repository"], dict)


def test_dict_intake_checksum_is_canonical_and_stable() -> None:
    a = {"iplan_id": "P", "context_package": {"repository": "."}, "work_order": {"todos": []}}
    b = {"context_package": {"repository": "."}, "work_order": {"todos": []}, "iplan_id": "P"}  # reordered
    ca = ingest_task_payload_dict(a)["intake_control"]["source_iplan_checksum"]
    cb = ingest_task_payload_dict(b)["intake_control"]["source_iplan_checksum"]
    assert ca == cb and ca.startswith("sha256:")  # key order does not change the canonical hash


def test_verify_bearer() -> None:
    assert verify_bearer("Bearer s3cret", "s3cret") is True
    assert verify_bearer("Bearer wrong", "s3cret") is False
    assert verify_bearer("s3cret", "s3cret") is False  # missing "Bearer " prefix
    assert verify_bearer(None, "s3cret") is False
    assert verify_bearer("Bearer s3cret", "") is False  # empty expected never matches
