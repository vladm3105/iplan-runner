"""Gated fake-iplanic integration suite (D-4b Task 4).

Opt-in, not in CI (PLAN-008 pattern): set ``IPLAN_FAKE_IPLANIC=1`` to run. Spins an
in-process ``POST /v1/events`` server on loopback and drives the real relay client
+ drain worker against it, asserting the full delivery contract: 202 + idempotent
replay, every reject -> outcome, dead-letter-doesn't-stall, and auth refresh-once.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
import yaml
from iplan_claude.ledger.persistence import load
from iplan_claude.relay import store as relay_store
from iplan_claude.relay.client import IplanicClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("IPLAN_FAKE_IPLANIC"),
    reason="gated integration suite; set IPLAN_FAKE_IPLANIC=1 to run (not in CI, PLAN-008 pattern)",
)

ROOT = Path(__file__).resolve().parents[3]
ACCEPT = ROOT / "framework" / "conformance" / "remote" / "accept"
KEY = b"conformance-key"
FAR_FUTURE = datetime(2099, 1, 1, tzinfo=UTC)


@contextmanager
def fake_server(responder: Callable[[int], tuple[int, dict[str, Any]]]) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Run an in-process ``/v1/events`` server; ``responder(n)`` picks each reply."""
    received: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server override name
            n = len(received)
            length = int(self.headers.get("Content-Length") or 0)
            event = json.loads(self.rfile.read(length)) if length else {}
            received.append({"auth": self.headers.get("Authorization"), "event": event})
            status, body = responder(n)
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args: Any) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", received
    finally:
        server.shutdown()
        server.server_close()


def _fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    ledger = load(ACCEPT / "ledger.yaml")
    payload = yaml.safe_load((ACCEPT / "payload.yaml").read_text())
    return ledger, payload


def _client(endpoint: str, token: str = "tok", max_retries: int = 2) -> IplanicClient:
    return IplanicClient(endpoint, lambda: token, max_retries=max_retries, backoff_base=0.0)


def _drain(endpoint_client: IplanicClient, store: Path, **kw: Any) -> Any:
    from iplan_claude.relay.worker import drain

    ledger, payload = _fixture()
    return drain(ledger, payload, client=endpoint_client, store_dir=str(store), ledger_id="L", key=KEY, **kw)


def test_202_and_idempotent_replay(tmp_path: Path) -> None:
    with fake_server(lambda n: (202, {})) as (endpoint, received):
        rep1 = _drain(_client(endpoint), tmp_path)
        rep2 = _drain(_client(endpoint), tmp_path)
    assert rep1.ok and rep1.delivered
    assert rep2.delivered == []  # the durable cursor prevents a resend
    keys = [r["event"]["idempotency_key"] for r in received]
    assert len(keys) == len(set(keys)) == len(rep1.delivered)  # distinct keys — no fan-out collision


def test_403_dead_letters_and_continues(tmp_path: Path) -> None:
    with fake_server(lambda n: (403, {}) if n == 0 else (202, {})) as (endpoint, _received):
        rep = _drain(_client(endpoint), tmp_path)
    assert len(rep.dead_lettered) == 1
    assert rep.delivered and rep.ok  # continued past the dead-letter — did not stall (R3)
    dl = relay_store.load_dead_letter(str(tmp_path), "L")
    assert len(dl) == 1 and "registration/scope" in dl[0]["reason"]


def test_timestamp_skew_far_stale_dead_letters(tmp_path: Path) -> None:
    skew = {"reject_code": "timestamp_skew"}
    with fake_server(lambda n: (409, skew) if n == 0 else (202, {})) as (endpoint, _received):
        rep = _drain(_client(endpoint), tmp_path, now=FAR_FUTURE, max_age_s=0)
    assert len(rep.dead_lettered) == 1  # far older than max_age_s -> dead-letter
    assert rep.delivered and rep.ok


def test_timestamp_skew_within_window_retries(tmp_path: Path) -> None:
    skew = {"reject_code": "timestamp_skew"}
    with fake_server(lambda n: (409, skew)) as (endpoint, _received):
        rep = _drain(_client(endpoint), tmp_path, now=FAR_FUTURE, max_age_s=10**12)
    assert rep.pending and not rep.delivered and not rep.dead_lettered
    assert rep.ok  # a retry is not a halt
    assert relay_store.load_settled(str(tmp_path), "L") == set()  # cursor did not advance


def test_invalid_signature_halts(tmp_path: Path) -> None:
    with fake_server(lambda n: (422, {"reject_code": "invalid_signature"})) as (endpoint, _received):
        rep = _drain(_client(endpoint), tmp_path)
    assert rep.halted and not rep.ok
    assert not rep.delivered and not rep.dead_lettered


def test_server_error_retries_then_pending(tmp_path: Path) -> None:
    with fake_server(lambda n: (503, {})) as (endpoint, received):
        rep = _drain(_client(endpoint, max_retries=1), tmp_path)
    assert rep.pending and not rep.delivered and rep.ok
    assert len(received) >= 2  # the client retried the first event before giving up


def test_auth_refresh_once_succeeds(tmp_path: Path) -> None:
    calls = {"n": 0}

    def provider() -> str:
        calls["n"] += 1
        return "stale" if calls["n"] == 1 else "fresh"

    with fake_server(lambda n: (401, {}) if n == 0 else (202, {})) as (endpoint, received):
        client = IplanicClient(endpoint, provider, max_retries=2, backoff_base=0.0)
        rep = _drain(client, tmp_path)
    assert rep.ok and rep.delivered
    assert received[0]["auth"] == "Bearer stale"
    assert received[1]["auth"] == "Bearer fresh"  # refreshed token used on retry


def test_auth_refresh_fails_halts(tmp_path: Path) -> None:
    with fake_server(lambda n: (401, {})) as (endpoint, _received):
        client = IplanicClient(endpoint, lambda: "stale", max_retries=2, backoff_base=0.0)
        rep = _drain(client, tmp_path)
    assert rep.halted and not rep.ok and not rep.delivered
