"""Signature & hash coverage for IPLANIC signed surfaces (PLAN-001 Task 4).

The signed payload of an ``execution-event`` is the event minus
``{signature, received_at}`` (``received_at`` is ingest-stamped), after drop-null
normalization. ``signature.value`` is lowercase hex of the raw signature bytes.
See docs/standards/IPLAN-CANONICALIZATION.md and IPLAN-DEFINITIONS.md.
"""

import hashlib
import hmac

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .canonical import canonical_hash, canonicalize, drop_null

#: Event fields excluded from the signed payload.
EXCLUDED_EVENT_FIELDS = ("signature", "received_at")
SIGNATURE_ALGORITHMS = ("hmac-sha256", "ed25519")


def signing_payload(event):
    """Return the signed-payload view of an ``execution-event``: the event minus
    ``signature`` and ``received_at``, drop-null normalized."""
    return drop_null({k: v for k, v in event.items() if k not in EXCLUDED_EVENT_FIELDS})


def evidence_seal_hash(payload, evidence_manifest):
    """Return the evidence-bundle seal hash: ``canonical_hash`` over the canonical
    payload **and** the evidence manifest (IPLAN-DEFINITIONS.md)."""
    return canonical_hash({"payload": payload, "evidence_manifest": evidence_manifest})


def sign(payload, *, algorithm, key):
    """Sign the canonical bytes of ``payload``; return lowercase-hex
    ``signature.value``.

    ``key`` is the HMAC secret (``hmac-sha256``) or the 32-byte ed25519 private
    seed (``ed25519``).
    """
    data = canonicalize(payload)
    if algorithm == "hmac-sha256":
        return hmac.new(key, data, hashlib.sha256).hexdigest()
    if algorithm == "ed25519":
        return Ed25519PrivateKey.from_private_bytes(key).sign(data).hex()
    raise ValueError(f"unsupported algorithm: {algorithm!r}")


def verify(payload, value, *, algorithm, key):
    """Verify ``value`` (hex) against ``payload``.

    ``key`` is the HMAC secret (``hmac-sha256``) or the 32-byte ed25519 public
    key (``ed25519``).
    """
    data = canonicalize(payload)
    if algorithm == "hmac-sha256":
        expected = hmac.new(key, data, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, value)
    if algorithm == "ed25519":
        try:
            Ed25519PublicKey.from_public_bytes(key).verify(bytes.fromhex(value), data)
            return True
        except InvalidSignature:
            return False
    raise ValueError(f"unsupported algorithm: {algorithm!r}")
