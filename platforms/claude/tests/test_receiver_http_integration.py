"""Non-gated integration for the M-body guard (PLAN-025 P3): a malformed / oversized
``Content-Length`` must get a clean 400/413 from the live receiver — NOT crash the
handler thread (the original bug) — and the server must keep serving afterwards.

Socket-level (raw request) because urllib/http.client compute Content-Length
themselves; this drives the real `build_receiver` server over loopback.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from iplan_claude.engine import ClaudeEngine
from iplan_claude.receiver import ReceiverDeps, build_receiver
from iplan_claude.relay.client import IplanicClient

TOKEN = "tok"


@contextmanager
def _server(tmp_path: Path) -> Iterator[tuple[str, int]]:
    deps = ReceiverDeps(
        engine=ClaudeEngine(),
        store_dir=str(tmp_path),
        workspace=str(tmp_path),
        client=IplanicClient("http://127.0.0.1:1", lambda: "t", backoff_base=0.0),
        key=b"k",
        key_id="k1",
    )
    server = build_receiver(bind="127.0.0.1", port=0, token=TOKEN, deps=deps)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield "127.0.0.1", server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def _status_line(host: str, port: int, content_length: str) -> str:
    req = (
        f"POST /v1/tasks HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer {TOKEN}\r\n"
        f"Content-Length: {content_length}\r\nConnection: close\r\n\r\n"
    )
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(req.encode())
        sock.settimeout(5)
        data = b""
        while b"\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    return data.split(b"\r\n", 1)[0].decode(errors="replace")


def test_malformed_content_length_returns_400_and_server_survives(tmp_path: Path) -> None:
    with _server(tmp_path) as (host, port):
        assert "400" in _status_line(host, port, "not-a-number")
        # The handler thread survived — a follow-up request is still served (also 400,
        # a fresh malformed one, proving the server keeps answering).
        assert "400" in _status_line(host, port, "-1")


def test_oversized_content_length_returns_413(tmp_path: Path) -> None:
    with _server(tmp_path) as (host, port):
        assert "413" in _status_line(host, port, "1073741824")  # 1 GiB declared
