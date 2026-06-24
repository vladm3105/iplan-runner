"""Canonicalization/signing — a re-export shim over the vendored IPLAN standard (PLAN-023, D-0023).

The reference ``iplan-canonical-json`` + signing implementation is vendored verbatim from
``iplan-standard@iplan/v0.1.0`` in ``security/iplan_canonical/`` (do not edit — see that package). This module
preserves the historical ``security.iplanic_signing`` public surface by re-exporting it, so every existing
importer and the conformance suite are unchanged. ``import x as x`` form satisfies mypy ``--strict``
``no_implicit_reexport``.
"""

from __future__ import annotations

from .iplan_canonical.canonical import CANONICALIZATION_ALGORITHM as CANONICALIZATION_ALGORITHM
from .iplan_canonical.canonical import HASH_ALGORITHM as HASH_ALGORITHM
from .iplan_canonical.canonical import canonical_hash as canonical_hash
from .iplan_canonical.canonical import canonicalize as canonicalize
from .iplan_canonical.canonical import drop_null as drop_null
from .iplan_canonical.signing import EXCLUDED_EVENT_FIELDS as EXCLUDED_EVENT_FIELDS
from .iplan_canonical.signing import SIGNATURE_ALGORITHMS as SIGNATURE_ALGORITHMS
from .iplan_canonical.signing import sign as sign
from .iplan_canonical.signing import signing_payload as signing_payload
from .iplan_canonical.signing import verify as verify

__all__ = [
    "CANONICALIZATION_ALGORITHM",
    "HASH_ALGORITHM",
    "EXCLUDED_EVENT_FIELDS",
    "SIGNATURE_ALGORITHMS",
    "canonicalize",
    "canonical_hash",
    "drop_null",
    "signing_payload",
    "sign",
    "verify",
]
