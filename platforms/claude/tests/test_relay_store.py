"""Unit tests for the SQLite relay operational store (D-4c).

Network-free and CI-safe (unlike the gated transport suite). Proves the outbox
semantics: a dead-letter write is an atomic settle, a dead-lettered key is never
flipped to delivered, state survives across connections (WAL), concurrent writers
do not error, and identity round-trips.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from iplan_claude.relay import store

_IDENTITY = (
    "org_id",
    "project_id",
    "iplan_id",
    "plan_version_id",
    "run_id",
    "task_id",
    "step_id",
    "executor_id",
)


def _event(key: str) -> dict[str, Any]:
    return {"idempotency_key": key, "event_type": "task.started"}


def test_mark_settled_roundtrip(tmp_path: Path) -> None:
    store.mark_settled(str(tmp_path), "L", "k1")
    assert store.load_settled(str(tmp_path), "L") == {"k1"}


def test_dead_letter_is_atomic_settle(tmp_path: Path) -> None:
    store.dead_letter(str(tmp_path), "L", {"event": _event("k1"), "reason": "403 registration/scope"})
    # one call settles AND records the dead-letter — no separate cursor write
    assert "k1" in store.load_settled(str(tmp_path), "L")
    dl = store.load_dead_letter(str(tmp_path), "L")
    assert len(dl) == 1
    assert dl[0]["reason"] == "403 registration/scope"
    assert dl[0]["event"]["idempotency_key"] == "k1"


def test_dead_lettered_key_not_flipped_by_mark_settled(tmp_path: Path) -> None:
    store.dead_letter(str(tmp_path), "L", {"event": _event("k1"), "reason": "halted"})
    store.mark_settled(str(tmp_path), "L", "k1")  # INSERT OR IGNORE — must not flip the status
    dl = store.load_dead_letter(str(tmp_path), "L")
    assert len(dl) == 1 and dl[0]["reason"] == "halted"


def test_persistence_across_connections(tmp_path: Path) -> None:
    store.mark_settled(str(tmp_path), "L", "k1")
    store.dead_letter(str(tmp_path), "L", {"event": _event("k2"), "reason": "r"})
    # each call opens a fresh connection — WAL data persists
    assert store.load_settled(str(tmp_path), "L") == {"k1", "k2"}


def test_idempotent_reinsert(tmp_path: Path) -> None:
    store.mark_settled(str(tmp_path), "L", "k1")
    store.mark_settled(str(tmp_path), "L", "k1")
    assert store.load_settled(str(tmp_path), "L") == {"k1"}


def test_isolation_by_ledger_id(tmp_path: Path) -> None:
    store.mark_settled(str(tmp_path), "A", "k1")
    store.mark_settled(str(tmp_path), "B", "k2")
    assert store.load_settled(str(tmp_path), "A") == {"k1"}
    assert store.load_settled(str(tmp_path), "B") == {"k2"}


def test_concurrent_writers_do_not_error(tmp_path: Path) -> None:
    def writer(start: int) -> None:
        for i in range(start, start + 10):
            store.mark_settled(str(tmp_path), "L", f"k{i}")

    threads = [threading.Thread(target=writer, args=(s,)) for s in (0, 10, 20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # WAL + busy_timeout: 3 concurrent writers, no "database is locked"
    assert len(store.load_settled(str(tmp_path), "L")) == 30


def test_identity_roundtrip_and_return(tmp_path: Path) -> None:
    payload: dict[str, Any] = {f: f"v-{f}" for f in _IDENTITY}
    payload["extra"] = "ignored"
    saved = store.save_identity(str(tmp_path), "L", payload)
    assert saved["run_id"] == "v-run_id"
    assert "extra" not in saved  # only the 8 identity fields are persisted
    assert store.load_identity(str(tmp_path), "L") == saved


def test_load_identity_absent(tmp_path: Path) -> None:
    assert store.load_identity(str(tmp_path), "L") is None


def test_prune_settled_removes_old_settled_keeps_dead_letter_and_active(tmp_path: Path) -> None:
    # M-relay (PLAN-025 P3): a store-wide sweep deletes settled operational rows —
    # DELIVERED delivery rows + terminal accepted_task rows — but keeps dead-lettered
    # rows (operator visibility) and any still-active row. max_age_s=-1 puts the cutoff
    # in the future so every row passes the age filter and only the status filter decides.
    d = str(tmp_path)
    store.mark_settled(d, "L1", "k-delivered")
    store.dead_letter(d, "L1", {"event": {"idempotency_key": "k-dead"}, "reason": "bad"})
    store.accept_task(d, "R-done", "T")
    store.claim_task(d, "R-done", "T")
    store.settle_task(d, "R-done", "T", ok=True)
    store.accept_task(d, "R-run", "T")
    store.claim_task(d, "R-run", "T")  # left running (in-flight)
    store.accept_task(d, "R-acc", "T")  # left bare-accepted

    counts = store.prune_settled(d, max_age_s=-1)

    assert counts == {"delivery": 1, "accepted_task": 1}
    # load_settled reads every delivery row (delivered OR dead-lettered); the delivered
    # mark is pruned, the dead-letter row remains (still a settled-cursor entry).
    assert store.load_settled(d, "L1") == {"k-dead"}
    assert len(store.load_dead_letter(d, "L1")) == 1  # dead-letter kept
    assert store.task_status(d, "R-done", "T") is None  # terminal pruned
    assert store.task_status(d, "R-run", "T") == "running"  # active kept
    assert store.task_status(d, "R-acc", "T") == "accepted"  # accepted kept


def test_prune_settled_keeps_recent_rows(tmp_path: Path) -> None:
    d = str(tmp_path)
    store.mark_settled(d, "L1", "k")
    store.accept_task(d, "R", "T")
    store.claim_task(d, "R", "T")
    store.settle_task(d, "R", "T", ok=True)

    counts = store.prune_settled(d, max_age_s=10_000)  # nothing is 10000s old

    assert counts == {"delivery": 0, "accepted_task": 0}
    assert store.load_settled(d, "L1") == {"k"}
    assert store.task_status(d, "R", "T") == "done"
