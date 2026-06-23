"""iplan-canonical-json v1.0 — RFC 8785 JCS + sha256, with drop-null
normalization. See docs/standards/IPLAN-CANONICALIZATION.md (D-0021)."""

import hashlib

import rfc8785

CANONICALIZATION_ALGORITHM = "iplan-canonical-json"
CANONICALIZATION_VERSION = "1.0"
HASH_ALGORITHM = "sha256"


def drop_null(value):
    """Recursively drop object members whose value is ``None`` so that an absent
    optional field and an explicit ``null`` collapse to the same canonical form.
    """
    if isinstance(value, dict):
        return {k: drop_null(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [drop_null(v) for v in value]
    return value


def canonicalize(value):
    """Return the ``iplan-canonical-json`` (RFC 8785 JCS) UTF-8 bytes for ``value``,
    after drop-null normalization."""
    return rfc8785.dumps(drop_null(value))


def canonical_hash(value):
    """Return ``lowercasehex(sha256(canonicalize(value)))``."""
    return hashlib.sha256(canonicalize(value)).hexdigest()
