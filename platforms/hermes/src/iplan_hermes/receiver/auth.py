"""Constant-time bearer verification for the inbound task receiver (PLAN-021).

The receiver's auth is **mandatory**: the iplanic dispatcher attaches
`Authorization: Bearer <token>` when the executor declares a `dispatch_token_id`
(iplanic PLAN-048 / D-0067), and the shared token is provisioned to the receiver
out of band (`IOPS_RECEIVER_TOKEN`). The compare is constant-time
(`hmac.compare_digest`) so a wrong token leaks no timing signal.
"""

from __future__ import annotations

import hmac

_BEARER = "Bearer "


def verify_bearer(header_value: str | None, expected: str) -> bool:
    """True iff `header_value` is `Bearer <token>` with `token` equal to `expected`
    (constant-time). A missing/malformed header or an empty `expected` is False."""
    if not expected or not header_value or not header_value.startswith(_BEARER):
        return False
    token = header_value[len(_BEARER) :]
    return hmac.compare_digest(token, expected)
