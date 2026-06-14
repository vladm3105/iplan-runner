"""iplan-canonical-json signer for Iplanic ``execution-event`` emission.

Vendored mirror of Iplanic's ``iplan-canonical-json`` (RFC 8785 JCS + ``sha256``
with recursive drop-null) and its signature coverage: the signed
``execution-event`` payload is the event minus ``{signature, received_at}``,
drop-null normalized; ``signature.value`` is lowercase hex of the raw signature
bytes. See the Iplanic standard ``docs/standards/IPLAN-CANONICALIZATION.md``
(D-0021) and reference module ``iplan_canonical/``.

This is kept **separate** from the standalone authenticated ledger
(``security/signing.py``, ``sign_event``/hash-chain), which is unchanged.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, cast

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

CANONICALIZATION_ALGORITHM = "iplan-canonical-json"
HASH_ALGORITHM = "sha256"
#: Event fields excluded from the signed payload (``received_at`` is ingest-stamped).
EXCLUDED_EVENT_FIELDS = ("signature", "received_at")
SIGNATURE_ALGORITHMS = ("hmac-sha256", "ed25519")


def drop_null(value: Any) -> Any:
    """Recursively drop object members whose value is ``None`` so an absent
    optional field and an explicit ``null`` collapse to the same canonical form."""
    if isinstance(value, dict):
        return {k: drop_null(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [drop_null(v) for v in value]
    return value


def canonicalize(value: Any) -> bytes:
    """Return the ``iplan-canonical-json`` (RFC 8785 JCS) UTF-8 bytes for ``value``,
    after drop-null normalization."""
    return rfc8785.dumps(drop_null(value))


def canonical_hash(value: Any) -> str:
    """Return ``lowercasehex(sha256(canonicalize(value)))``."""
    return hashlib.sha256(canonicalize(value)).hexdigest()


def signing_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Return the signed-payload view of an ``execution-event``: the event minus
    ``{signature, received_at}``, drop-null normalized."""
    return cast(
        "dict[str, Any]",
        drop_null({k: v for k, v in event.items() if k not in EXCLUDED_EVENT_FIELDS}),
    )


def sign(payload: Any, *, algorithm: str, key: bytes) -> str:
    """Sign the canonical bytes of ``payload``; return lowercase-hex signature value.

    ``key`` is the raw HMAC secret bytes (``hmac-sha256``) or the 32-byte ed25519
    private seed (``ed25519``). The caller assembles the event ``signature`` object
    ``{key_id, algorithm, value}`` from this value and the executor's registered key.
    """
    data = canonicalize(payload)
    if algorithm == "hmac-sha256":
        return hmac.new(key, data, hashlib.sha256).hexdigest()
    if algorithm == "ed25519":
        return Ed25519PrivateKey.from_private_bytes(key).sign(data).hex()
    raise ValueError(f"unsupported algorithm: {algorithm!r}")


def verify(payload: Any, value: str, *, algorithm: str, key: bytes) -> bool:
    """Verify hex ``value`` against ``payload``. ``key`` is the HMAC secret bytes
    or the 32-byte ed25519 public key."""
    data = canonicalize(payload)
    if algorithm == "hmac-sha256":
        return hmac.compare_digest(hmac.new(key, data, hashlib.sha256).hexdigest(), value)
    if algorithm == "ed25519":
        try:
            Ed25519PublicKey.from_public_bytes(key).verify(bytes.fromhex(value), data)
            return True
        except InvalidSignature:
            return False
    raise ValueError(f"unsupported algorithm: {algorithm!r}")
