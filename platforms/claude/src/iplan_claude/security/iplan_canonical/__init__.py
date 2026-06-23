"""Reference implementation of ``iplan-canonical-json`` (RFC 8785 JCS) and the
IPLANIC signature/hash coverage rules. See docs/standards/IPLAN-CANONICALIZATION.md.
"""

from .canonical import (
    CANONICALIZATION_ALGORITHM,
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    canonical_hash,
    canonicalize,
    drop_null,
)
from .signing import (
    SIGNATURE_ALGORITHMS,
    evidence_seal_hash,
    sign,
    signing_payload,
    verify,
)

__all__ = [
    "CANONICALIZATION_ALGORITHM",
    "CANONICALIZATION_VERSION",
    "HASH_ALGORITHM",
    "SIGNATURE_ALGORITHMS",
    "canonicalize",
    "canonical_hash",
    "drop_null",
    "signing_payload",
    "evidence_seal_hash",
    "sign",
    "verify",
]
