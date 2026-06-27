"""Gated end-to-end wire test for the inbound A2A task receiver (PLAN-021).

Opt-in, not in CI (PLAN-008 pattern): set ``IPLAN_FAKE_IPLANIC=1`` to run. Spins
the real receiver (`POST /v1/tasks`) AND an in-process iplanic `POST /v1/events`
fake on loopback, then drives a dispatch through the whole chain — accept → run a
deterministic executor → drain signed events back — asserting **the events
actually reach the fake** (the central claim), plus the 401 / 400 / 503 /
idempotent-replay / concurrent-race paths.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from iplan_claude.engine import ClaudeEngine
from iplan_claude.receiver import ReceiverDeps, build_receiver
from iplan_claude.relay.client import IplanicClient, Response

pytestmark = pytest.mark.skipif(
    not os.environ.get("IPLAN_FAKE_IPLANIC"),
    reason="gated wire suite; set IPLAN_FAKE_IPLANIC=1 to run (not in CI, PLAN-008 pattern)",
)

TOKEN = "receiver-tok"
# A deterministic default-executor run over the single-todo payload below projects
# exactly 3 execution-events (task.started + task.completed + test.failed). The
# exact count also guards the dedup tests: a double-run would deliver 6, not 3.
RUN_EVENTS = 3


def _payload(run_id: str = "RUN-01", task_id: str = "TASK-01") -> dict[str, Any]:
    """A valid dispatched task with the OBJECT repository shape iplanic sends."""
    return {
        "iplan_id": "IPLAN-01",
        "plan_version_id": "PV-01",
        "org_id": "org-a",
        "project_id": "proj-1",
        "run_id": run_id,
        "step_id": "STEP-001",
        "task_id": task_id,
        "executor_id": "exec:iopsremote2zqf7kx3a",
        "work_order": {
            "work_order_id": "WORK-001",
            "todos": [{"todo_id": "TODO-1", "description": "do", "acceptance_criteria": ["ok"]}],
        },
        "context_package": {
            "repository": {"url": "https://x/r.git", "default_branch": "main", "base_ref": "abc"},
            "forbidden_paths": [".git"],
        },
    }


@contextmanager
def fake_events(status: int = 202) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """An in-process iplanic `POST /v1/events`; records each received event."""
    received: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            received.append(json.loads(self.rfile.read(length)) if length else {})
            self.send_response(status)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *a: Any) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", received
    finally:
        server.shutdown()
        server.server_close()


@contextmanager
def receiver(tmp_path: Path, *, client: Any, max_parallel: int = 4) -> Iterator[str]:
    """Start the real receiver with an injected drain `client`; yield its base URL."""
    deps = ReceiverDeps(
        engine=ClaudeEngine(),
        store_dir=str(tmp_path),
        workspace=str(tmp_path),
        client=client,
        key=b"conformance-key",
        key_id="key-1",
    )
    server = build_receiver(bind="127.0.0.1", port=0, token=TOKEN, deps=deps, max_parallel=max_parallel)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _post(
    endpoint: str, payload: dict[str, Any] | None, *, token: str | None = TOKEN, raw: bytes | None = None
) -> tuple[int, dict[str, Any]]:
    body = raw if raw is not None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(endpoint + "/v1/tasks", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:  # nosec B310 - loopback test server
            return int(resp.status), json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return int(exc.code), json.loads(exc.read() or b"{}")


def _wait(predicate: Callable[[], bool], timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_dispatch_delivers_events_end_to_end(tmp_path: Path) -> None:
    with fake_events() as (events_url, received):
        client = IplanicClient(events_url, lambda: "tok", backoff_base=0.0)
        with receiver(tmp_path, client=client) as rx:
            status, body = _post(rx, _payload())
            assert status == 202 and body["status"] == "accepted"
            assert _wait(lambda: len(received) >= RUN_EVENTS), f"only {len(received)} events delivered"
    keys = [e["idempotency_key"] for e in received]
    assert len(keys) == len(set(keys)) == RUN_EVENTS  # the wire carried one run's distinct events
    assert all(e["signature"]["key_id"] == "key-1" for e in received)  # signed with receiver_key_id


def test_idempotent_replay_is_one_run(tmp_path: Path) -> None:
    with fake_events() as (events_url, received):
        client = IplanicClient(events_url, lambda: "tok", backoff_base=0.0)
        with receiver(tmp_path, client=client) as rx:
            s1, _ = _post(rx, _payload())
            assert s1 == 202
            assert _wait(lambda: len(received) >= RUN_EVENTS)
            s2, body2 = _post(rx, _payload())  # same (run_id, task_id) after it settled
            assert s2 == 202 and body2["status"] == "duplicate"
            time.sleep(0.2)  # give any (erroneous) second run a chance to deliver
    assert len(received) == RUN_EVENTS  # exactly one run delivered — the replay did not re-run


def test_bad_bearer_401(tmp_path: Path) -> None:
    with fake_events() as (events_url, received):
        client = IplanicClient(events_url, lambda: "tok", backoff_base=0.0)
        with receiver(tmp_path, client=client) as rx:
            assert _post(rx, _payload(), token="wrong")[0] == 401
            assert _post(rx, _payload(), token=None)[0] == 401
            time.sleep(0.2)
    assert received == []  # an unauthenticated dispatch runs nothing


def test_malformed_repository_400(tmp_path: Path) -> None:
    bad = _payload()
    bad["context_package"]["repository"] = {"url": "u", "default_branch": "main"}  # missing base_ref
    with fake_events() as (events_url, received):
        client = IplanicClient(events_url, lambda: "tok", backoff_base=0.0)
        with receiver(tmp_path, client=client) as rx:
            status, body = _post(rx, bad)
            assert status == 400 and body["detail"] == "REMOTE.PAYLOAD_REPOSITORY_SHAPE"
            assert _post(rx, None, raw=b"{not json")[0] == 400  # not JSON
            time.sleep(0.2)
    assert received == []


def test_at_capacity_503(tmp_path: Path) -> None:
    gate = threading.Event()
    started = threading.Event()

    class GateClient:
        """Blocks in the first delivery so the single worker slot stays occupied."""

        def deliver(self, event: dict[str, Any]) -> Response:
            started.set()
            gate.wait(5)
            return Response(status=202, body={})

    with receiver(tmp_path, client=GateClient(), max_parallel=1) as rx:
        assert _post(rx, _payload(run_id="RUN-A"))[0] == 202  # occupies the only slot
        assert started.wait(5)  # the worker is now blocked in delivery
        assert _post(rx, _payload(run_id="RUN-B"))[0] == 503  # no slot -> receiver_busy
        gate.set()  # release the first worker


def test_concurrent_same_task_runs_once(tmp_path: Path) -> None:
    with fake_events() as (events_url, received):
        client = IplanicClient(events_url, lambda: "tok", backoff_base=0.0)
        with receiver(tmp_path, client=client, max_parallel=8) as rx:
            results: list[int] = []

            def fire() -> None:
                results.append(_post(rx, _payload())[0])  # identical (run_id, task_id)

            threads = [threading.Thread(target=fire) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert all(s == 202 for s in results)
            assert _wait(lambda: len(received) >= RUN_EVENTS)
            time.sleep(0.3)  # let any duplicate run (if the dedup were broken) deliver too
    keys = [e["idempotency_key"] for e in received]
    assert len(keys) == len(set(keys)) == RUN_EVENTS  # exactly one run despite 8 concurrent POSTs
