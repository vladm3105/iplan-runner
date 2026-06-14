"""Probe HTTP server serving the manifest's health/readiness/startup paths."""

from __future__ import annotations

import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


def probe_server(manifest: dict[str, Any], health: Callable[[], dict[str, Any]] | None = None) -> HTTPServer:
    health_fn = health or (lambda: {"status": "ok"})
    probes = manifest.get("probes", {})
    paths = {p for p in probes.values() if isinstance(p, str)}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            if self.path in paths:
                body = json.dumps(health_fn()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            return None

    return HTTPServer(("127.0.0.1", 0), _Handler)
