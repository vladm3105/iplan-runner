"""Map an iplanic ``POST /v1/events`` response to a delivery outcome (D-4b).

The classifier ratified in PLAN-017 / D-0020: ``202`` advances; ``timestamp_skew``
uses a local far-stale heuristic (dead-letter vs retry); integrity rejects halt;
registration/scope (``403``) dead-letters; ``401`` triggers a single refresh;
transport/``5xx`` retries. Unknown rejects halt (fail safe, never silently drop).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .client import Response

#: Outcome actions.
ADVANCE = "advance"  # accepted (202) — settle, continue
RETRY = "retry"  # transient — stop draining, leave for the next sync
DEAD_LETTER = "dead_letter"  # terminal-but-skippable — record, settle, continue
HALT = "halt"  # integrity failure — stop the whole drain
REFRESH = "refresh"  # auth expired — refresh the token once, then retry

#: Far-stale threshold for ``timestamp_skew``: older → dead-letter, else retry.
DEFAULT_MAX_AGE_S = 86400


@dataclass(frozen=True)
class Outcome:
    action: str
    reason: str


def _event_age_s(event: dict[str, Any], now: datetime) -> float | None:
    occurred = event.get("occurred_at")
    if not isinstance(occurred, str):
        return None
    try:
        ts = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (now - ts).total_seconds()


def classify(
    response: Response, event: dict[str, Any], *, now: datetime, max_age_s: int = DEFAULT_MAX_AGE_S
) -> Outcome:
    status = response.status
    if status == 202:
        return Outcome(ADVANCE, "accepted")
    if status == 401:
        return Outcome(REFRESH, "unauthorized")
    if status == 403:
        return Outcome(DEAD_LETTER, "registration/scope rejected")
    if status >= 500:
        return Outcome(RETRY, f"server error {status}")
    code = response.body.get("reject_code") or response.body.get("code")
    if code == "timestamp_skew":
        age = _event_age_s(event, now)
        if age is not None and age > max_age_s:
            return Outcome(DEAD_LETTER, f"timestamp_skew, far-stale ({int(age)}s)")
        return Outcome(RETRY, "timestamp_skew, within window")
    if code in ("invalid_signature", "schema_invalid"):
        return Outcome(HALT, f"integrity: {code}")
    return Outcome(HALT, f"unhandled reject (status {status}, code {code})")
