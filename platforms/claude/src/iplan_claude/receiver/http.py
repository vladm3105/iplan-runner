"""The inbound A2A task door: `POST /v1/tasks` (PLAN-021).

Stdlib `http.server` only (`ThreadingHTTPServer`). The handler is deliberately
thin and **prompt-ACK-then-background**: iplanic maps any non-2xx / timeout to a
`DispatchError` and reads only the response status, so a long run must not block
the ACK. Each accepted task runs on its own daemon thread; the run + drain live in
`service.execute`.

Contract (also in `framework/remote/REMOTE_EXECUTOR_CONTRACT.md`):

* **mandatory** `Authorization: Bearer <token>` (constant-time) — else `401`.
* body = a `task.schema.json` payload; not-JSON / not-object / failing
  `validate_payload` → `400 schema_invalid`; missing `task_id` → `400`.
* idempotent on `(run_id, task_id)`: a row already `running`/terminal short-circuits
  to `202` (`status: duplicate`); a fresh or crash-orphaned accept runs.
* at capacity (`max_parallel` in flight) → `503 receiver_busy` (iplanic records a
  `DispatchError`, no attempt; the durable `accepted` row re-runs on re-dispatch).
* any `2xx` = accepted (the `{task_id, run_id, status}` body is debug-only).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from ..relay import store
from ..validation.payload_rules import validate_payload
from .auth import verify_bearer
from .service import ReceiverDeps, execute

_TASKS_PATH = "/v1/tasks"


class ReceiverServer(ThreadingHTTPServer):
    """A `ThreadingHTTPServer` carrying the receiver's wiring + a bounded run pool."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], *, token: str, deps: ReceiverDeps, max_parallel: int) -> None:
        super().__init__(address, _Handler)
        self.token = token
        self.deps = deps
        self.slots = threading.Semaphore(max_parallel)


class _Handler(BaseHTTPRequestHandler):
    server: ReceiverServer  # narrows the base annotation for the typed attrs below

    def _reply(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802 - http.server override name
        server = self.server
        deps = server.deps
        if self.path != _TASKS_PATH:
            return self._reply(404, {"reason": "not_found"})
        if not verify_bearer(self.headers.get("Authorization"), server.token):
            deps.log("401 unauthenticated")
            return self._reply(401, {"reason": "unauthenticated"})

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload: Any = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return self._reply(400, {"reason": "schema_invalid", "detail": "body is not valid JSON"})
        if not isinstance(payload, dict):
            return self._reply(400, {"reason": "schema_invalid", "detail": "body must be a JSON object"})

        findings = validate_payload(payload)
        if findings:
            return self._reply(400, {"reason": "schema_invalid", "detail": findings[0].rule_id})
        run_id: str = payload["run_id"]  # validate_payload guaranteed run_id is present
        if not payload.get("task_id"):
            return self._reply(400, {"reason": "schema_invalid", "detail": "task payload missing task_id"})
        task_id: str = payload["task_id"]

        decision = store.accept_task(deps.store_dir, run_id, task_id)
        if decision == "replay":
            deps.log(f"replay run={run_id} task={task_id}")
            return self._reply(202, {"task_id": task_id, "run_id": run_id, "status": "duplicate"})

        if not server.slots.acquire(blocking=False):
            deps.log(f"503 receiver_busy run={run_id} task={task_id}")
            return self._reply(503, {"reason": "receiver_busy"})

        def _work() -> None:
            try:
                execute(payload, deps)
            finally:
                server.slots.release()

        threading.Thread(target=_work, daemon=True).start()
        deps.log(f"accepted run={run_id} task={task_id}")
        return self._reply(202, {"task_id": task_id, "run_id": run_id, "status": "accepted"})

    def log_message(self, *args: Any) -> None:
        return  # the receiver logs structurally via deps.log; silence the default access log


def build_receiver(*, bind: str, port: int, token: str, deps: ReceiverDeps, max_parallel: int = 4) -> ReceiverServer:
    """Construct the receiver server. **Refuses to start** if `token` is empty
    (mandatory bearer). Binding raises `OSError` (e.g. address in use) — the caller
    handles it."""
    if not token:
        raise ValueError("receiver auth token is empty (set IOPS_RECEIVER_TOKEN); refusing to start")
    return ReceiverServer((bind, port), token=token, deps=deps, max_parallel=max_parallel)
