"""B3 (PLAN-025): classify iplanic's real ``{"reason": ...}`` reject envelope.

iplanic emits the reject code under ``reason`` (not ``reject_code``), and returns
HTTP ``403`` for ``invalid_signature`` / ``400`` for ``timestamp_skew``. The
classifier must read ``reason`` and route the integrity codes to HALT *before* the
generic ``403`` dead-letter branch, else a transient clock skew stalls the drain and
a signature forgery is silently dead-lettered instead of halting.
"""

from __future__ import annotations

from datetime import UTC, datetime

from iplan_hermes.relay.client import Response
from iplan_hermes.relay.reject import ADVANCE, DEAD_LETTER, HALT, RETRY, classify

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _event(occurred_at: str = "2026-01-01T00:00:00+00:00") -> dict:
    return {"occurred_at": occurred_at}


def test_reason_invalid_signature_403_halts() -> None:
    r = Response(status=403, body={"reason": "invalid_signature"})
    assert classify(r, _event(), now=NOW).action == HALT


def test_reason_timestamp_skew_400_within_window_retries() -> None:
    r = Response(status=400, body={"reason": "timestamp_skew"})
    assert classify(r, _event(), now=NOW).action == RETRY


def test_reason_timestamp_skew_far_stale_dead_letters() -> None:
    r = Response(status=400, body={"reason": "timestamp_skew"})
    stale = _event("2020-01-01T00:00:00+00:00")
    assert classify(r, stale, now=NOW).action == DEAD_LETTER


def test_reason_schema_invalid_halts() -> None:
    r = Response(status=400, body={"reason": "schema_invalid"})
    outcome = classify(r, _event(), now=NOW)
    assert outcome.action == HALT
    assert "schema_invalid" in outcome.reason


def test_plain_403_without_integrity_reason_still_dead_letters() -> None:
    r = Response(status=403, body={"reason": "scope_denied"})
    assert classify(r, _event(), now=NOW).action == DEAD_LETTER


def test_202_advances() -> None:
    assert classify(Response(status=202, body={}), _event(), now=NOW).action == ADVANCE


def test_reject_code_key_still_supported_for_backward_compat() -> None:
    r = Response(status=422, body={"reject_code": "invalid_signature"})
    assert classify(r, _event(), now=NOW).action == HALT


def test_bodyless_403_dead_letters() -> None:
    # iplanic always carries a `reason`; a bodyless 403 is, by contract, a
    # registration/scope reject (not integrity) → dead-letter and continue.
    r = Response(status=403, body={})
    assert classify(r, _event(), now=NOW).action == DEAD_LETTER


def test_5xx_retries_even_when_body_carries_a_code() -> None:
    # Transport 5xx is checked before the body-code branches, so a stray machine
    # code in a 5xx body can never be mis-routed to HALT.
    r = Response(status=503, body={"reason": "invalid_signature"})
    assert classify(r, _event(), now=NOW).action == RETRY
