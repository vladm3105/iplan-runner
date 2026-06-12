# Vendored Iplanic conformance vectors

Version-pinned mirror of Iplanic's golden `iplan-canonical-json` vectors. These
are the shared contract: `security/iplanic_signing.py` must reproduce every value
here byte-for-byte (canonical bytes, `sha256`, and `hmac-sha256`/`ed25519`
signature `value`).

| Field | Value |
|---|---|
| Source repo | `iplanic` (sibling) |
| Source path | `tests/contract/canonicalization/vectors/*.json` |
| Iplanic `schema_version` | `1.3-draft` |
| Pinned commit | `fb5f46d` |
| Standard | `docs/standards/IPLAN-CANONICALIZATION.md` (D-0021) |

Re-pin by re-copying and bumping the commit; drift surfaces as a failing
conformance vector, not a runtime dependency on the Iplanic repo.
