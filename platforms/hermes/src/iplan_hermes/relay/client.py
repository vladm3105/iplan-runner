"""HTTP transport for iplanic ``POST /v1/events`` (D-4b).

Stdlib-only (`urllib`), with a bounded transport/5xx retry and an injected
bearer-token provider seam (the D-0015 auth boundary; tests inject a static
token). The HTTP call itself is injectable (`opener`) so unit tests and the
in-process fake server exercise the real classification path without a socket.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: Returns the current bearer token, or ``None`` when unauthenticated.
TokenProvider = Callable[[], "str | None"]

#: Injectable HTTP transport: ``(url, data, headers) -> (status, body_bytes)``.
Opener = Callable[[str, bytes, "dict[str, str]"], "tuple[int, bytes]"]


class TransportError(RuntimeError):
    """The endpoint was unreachable after the bounded retries."""


@dataclass(frozen=True)
class Response:
    status: int
    body: dict[str, Any]


def _urllib_open(url: str, data: bytes, headers: dict[str, str]) -> tuple[int, bytes]:
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"refusing non-HTTP(S) iplanic endpoint: {url!r}")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:  # nosec B310 - scheme guarded above; operator-configured
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()


class IplanicClient:
    """POSTs signed execution-events verbatim to ``<endpoint>/v1/events``."""

    def __init__(
        self,
        endpoint: str,
        token_provider: TokenProvider,
        *,
        max_retries: int = 3,
        backoff_base: float = 0.0,
        opener: Opener | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._url = endpoint.rstrip("/") + "/v1/events"
        self._token_provider = token_provider
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._open = opener or _urllib_open
        self._sleep = sleep

    def deliver(self, event: dict[str, Any]) -> Response:
        """POST one event. Retries transport errors / 5xx; returns the final response."""
        data = json.dumps(event).encode()
        attempt = 0
        while True:
            headers = {"Content-Type": "application/json"}
            token = self._token_provider()
            if token:
                headers["Authorization"] = f"Bearer {token}"
            try:
                status, raw = self._open(self._url, data, headers)
            except (urllib.error.URLError, OSError) as exc:
                if attempt >= self._max_retries:
                    raise TransportError(str(exc)) from exc
                self._backoff(attempt)
                attempt += 1
                continue
            if status >= 500 and attempt < self._max_retries:
                self._backoff(attempt)
                attempt += 1
                continue
            return Response(status=status, body=_parse_body(raw))

    def _backoff(self, attempt: int) -> None:
        if self._backoff_base:
            self._sleep(self._backoff_base * (2**attempt))


def _parse_body(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed: Any = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
