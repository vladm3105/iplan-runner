"""Background heartbeat (PLAN-021): keep the receiver dispatchable.

iplanic refuses dispatch to a `stale` executor, so a long-lived receiver posts
`POST /executors/{id}/heartbeat` on an interval. That endpoint **requires**
`X-Org-Id` (unlike `/v1/events`, which is org-scoped via the signed body), so this
is a small stdlib poster — not `IplanicClient`, which hard-wires `/v1/events` and
exposes only `deliver`. Best-effort: a failed beat is logged, never fatal.
"""

from __future__ import annotations

import threading
import urllib.error
import urllib.request
from collections.abc import Callable

#: Injectable POST transport: ``(url, headers) -> status``.
Opener = Callable[[str, "dict[str, str]"], int]
TokenProvider = Callable[[], "str | None"]


def _urllib_post(url: str, headers: dict[str, str]) -> int:
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"refusing non-HTTP(S) heartbeat endpoint: {url!r}")
    req = urllib.request.Request(url, data=b"", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:  # nosec B310 - scheme guarded above; operator-configured
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def _noop(_message: str) -> None:
    return None


class Heartbeat:
    """A daemon thread posting executor liveness to iplanic every `interval_s`."""

    def __init__(
        self,
        *,
        endpoint: str,
        executor_id: str,
        org_id: str,
        token_provider: TokenProvider,
        interval_s: float,
        log: Callable[[str], None] = _noop,
        opener: Opener | None = None,
    ) -> None:
        self._url = endpoint.rstrip("/") + f"/executors/{executor_id}/heartbeat"
        self._org_id = org_id
        self._token_provider = token_provider
        self._interval_s = interval_s
        self._log = log
        self._open = opener or _urllib_post
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(self._interval_s):
            self.beat()

    def beat(self) -> int | None:
        """Post one heartbeat; return the status (or None on transport error)."""
        headers = {"X-Org-Id": self._org_id, "Content-Length": "0"}
        token = self._token_provider()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            status = self._open(self._url, headers)
        except Exception as exc:  # noqa: BLE001 - liveness is best-effort; log and keep beating
            self._log(f"heartbeat-failed: {exc!r}")
            return None
        self._log(f"heartbeat {status}")
        return status
