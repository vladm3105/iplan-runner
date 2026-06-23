# Vendored Iplanic conformance vectors

Version-pinned mirror of the IPLAN-standard golden `iplan-canonical-json` vectors. These
are the shared contract: `security/iplanic_signing.py` must reproduce every value
here byte-for-byte (canonical bytes, `sha256`, and `hmac-sha256`/`ed25519`
signature `value`).

| Field | Value |
|---|---|
| Source repo | `iplan-standard` |
| Source path | `tests/contract/canonicalization/vectors/*.json` |
| Pinned tag | `iplan/v0.1.0` |
| Standard | `docs/standards/IPLAN-CANONICALIZATION.md` (D-0021) |

Re-pin by re-copying from the new tag; drift is caught by `sync/check-drift.sh` (byte-diff vs the tag),
conformance vector, not a runtime dependency on the Iplanic repo.
