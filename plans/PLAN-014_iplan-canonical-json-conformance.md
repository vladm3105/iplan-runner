# PLAN-014 — Adopt `iplan-canonical-json` for Iplanic event signing

> **Goal:** make IOPS-emitted Iplanic `execution-event` signatures **byte-
> reproducible by Iplanic** by adopting Iplanic's normative `iplan-canonical-json`
> (RFC 8785 JCS + `sha256`) for the event signing path, and proving it against
> Iplanic's golden vectors. This is the canonicalization core that the re-grounded
> **PLAN-013** consumes (its Re-grounding §1). New decision **D-0017**.
>
> **Size:** one focused gap — IOPS's signing canonicalization is not Iplanic's.
> Not a rewrite of the standalone ledger signer, which is retained unchanged.

| Field | Value |
|---|---|
| Task | IOPS-PLAN-014 |
| Depends on | engine `security/signing.py`; Iplanic `iplan-canonical-json` (frozen — cross-repo note) |
| Status | DONE - 2026-06-11 |
| Feeds | PLAN-013 (Iplanic remote-executor conformance) — supplies its canonical signer |

## Problem

IOPS signs ledger events with `security.signing.sign_event` — `hmac.new(key.encode(),
_canonical(event), sha256)` where `_canonical` is
`json.dumps(sort_keys, separators)` excluding **only** `signature`. Iplanic's
frozen `iplan-canonical-json` is **RFC 8785 JCS** over `sha256` with recursive
**drop-null**, a signed payload excluding **`{signature, received_at}`**, an HMAC
keyed with the **raw key bytes**, and **`ed25519`** support. The two diverge on:

- canonical bytes (ECMAScript number formatting, Unicode handling, key ordering —
  JCS vs `json.dumps`);
- **drop-null** (Iplanic removes null values recursively; IOPS keeps them);
- **`received_at`** (IOPS signs it; Iplanic excludes it **and overwrites it at
  ingest**, so an IOPS signature fails verification);
- HMAC key encoding (raw bytes vs utf-8 of the key string);
- algorithm coverage (`ed25519` absent in IOPS).

Verified differentially against Iplanic's golden `sig_hmac` vector: IOPS `7ce5…` ≠
Iplanic `bcac…`. So IOPS is not a conformant signer today.

## Approach & decision (D-0017)

Add a **dedicated Iplanic signer** alongside the existing one; do not change the
standalone ledger path.

- New module `security/iplanic_signing.py` (copied identically into each engine —
  engine isolation), mirroring Iplanic's reference module: `drop_null(value)`,
  `canonicalize(value)` = `rfc8785.dumps(drop_null(value))`, `canonical_hash(value)`
  = lowercase-hex `sha256`, `signing_payload(event)` = drop `{signature,
  received_at}` then drop-null, and `sign(payload, *, algorithm, key)` /
  `verify(...)` for `hmac-sha256` (raw-byte key) and `ed25519`. Mirroring the
  Iplanic reference, **`sign` returns the lowercase-hex signature `value`** (a
  string); the event `signature` **object** `{key_id, algorithm, value}` is
  assembled by the consumer (PLAN-013's `to_execution_events`), which supplies
  `key_id`/`algorithm` from the executor's registered key. **HMAC keys with raw
  bytes** — IOPS's `signing_key` is a utf-8 `str` today, so the Iplanic path must
  decode/derive the registered key to bytes (Iplanic's vectors key with
  `bytes.fromhex`), not `str.encode()`.
- The legacy `sign_event` / `sign_ledger` / `verify_ledger` stay **unchanged** for
  the standalone authenticated ledger — they are not the Iplanic wire format.
- **Conformance:** vendor Iplanic's golden vectors (version-pinned, with their
  upstream `source` + version) and reproduce them byte-for-byte — the canonical
  bytes, the `sha256`, and the `hmac-sha256` / `ed25519` signature values.

## Tasks

### Task 1 — dependencies

Add `rfc8785>=0.1.4` (JCS) and `cryptography>=42` (ed25519) to **each** engine's
`pyproject.toml` `dependencies` (currently `["pyyaml>=6"]`).

### Task 2 — the canonical signer (per engine, identical copies)

Create `security/iplanic_signing.py` in **both** `iplan_hermes` and `iplan_claude`
with `drop_null`, `canonicalize`, `canonical_hash`, `signing_payload`, `sign`,
`verify` as above. Constants: `CANONICALIZATION_ALGORITHM = "iplan-canonical-json"`,
`HASH_ALGORITHM = "sha256"`. `sign` returns the lowercase-hex `value`; the
`{key_id, algorithm, value}` object is assembled by the caller (PLAN-013's
`to_execution_events`) — the schema's `additionalProperties: false` means only
those three keys.

### Task 3 — vendor Iplanic's golden vectors + conformance

- Vendor Iplanic's `canonicalization` vectors (`canon_*`, `normalize_omit_vs_null`),
  `sig_hmac`, `sig_ed25519`, and `seal_hash` under
  `framework/remote/iplanic-vectors/` (version-pinned; each records the upstream
  `source` path + the Iplanic `schema_version`/commit it mirrors).
- A conformance test (`tests/conformance/test_iplanic_signing.py`, or the existing
  `framework/conformance/` vector pattern) that, for each vendored vector, asserts
  `canonicalize`/`canonical_hash`/`sign` reproduce the recorded `canonical`,
  `sha256`, and signature `value` **byte-for-byte**. Run for both engine copies.

### Task 4 — decision + handoff

- `plans/DECISIONS.md`: add **D-0017** (adopt `iplan-canonical-json` for Iplanic
  emission; legacy `sign_event` retained for the standalone ledger).
- `CHANGELOG.md` + handoff note: PLAN-013 consumes this signer.

## Validation

- The new conformance reproduces every vendored Iplanic vector byte-for-byte (the
  hash/signature values match Iplanic's recorded values).
- `pytest` green in both engines; the standalone `sign_event` tests are unchanged.
- `pre-commit run --all-files` → all hooks pass (the plan-gate included).

## Out of scope

- The standalone authenticated-ledger signer (`sign_event` and the hash-chain) —
  retained unchanged; only the Iplanic-emission path is new.
- PLAN-013's payload intake, event projection, and sandbox `forbidden_paths` —
  those remain PLAN-013's scope; this plan only supplies the signer it consumes.
- A live transport / HTTP POST to Iplanic ingestion (PLAN-013 Out #1).
- Evidence-bundle `seal` emission (vendor `seal_hash` for the hasher; emitting
  sealed bundles is a later plan if IOPS contributes evidence upstream).

## Claim ledger

> Load-bearing **in-repo** claims, each citing the `file:line` verified this
> session. The Iplanic `iplan-canonical-json` contract is cross-repo (sibling
> `iplanic` repo) — outside the gate's reach — and is in the Cross-repo note,
> hand-verified against that repo, per the vendored-mirror stance.

| # | Claim | Symbol | Citation |
|---|-------|--------|----------|
| 1 | IOPS `_canonical` is `json.dumps(sort_keys)` excluding only `signature` — not JCS, no drop-null, and it includes `received_at` | `_canonical` | platforms/hermes/src/iplan_hermes/security/signing.py:13 |
| 2 | `sign_event` keys the HMAC with `key.encode()` (utf-8 of the key string, not raw bytes) | `key.encode` | platforms/hermes/src/iplan_hermes/security/signing.py:22 |
| 3 | the `security/signing.py` module is duplicated per engine (engine isolation), so the new signer goes in both | `_canonical` | platforms/claude/src/iplan_claude/security/signing.py:13 |
| 4 | each engine `pyproject.toml` lists only `pyyaml>=6` (no `rfc8785`/`cryptography`) | `pyyaml` | platforms/hermes/pyproject.toml:10 |
| 5 | IOPS conformance uses `expect.yaml` vector cases carrying a signature (the pattern reused for the vendored Iplanic vectors) | `signature` | framework/conformance/signing/minimal/expect.yaml:1 |
| 6 | the re-grounded PLAN-013 consumes this plan's canonical signer for Iplanic emission | `PLAN-014` | plans/PLAN-013_iplanic-remote-executor-conformance.md:57 |

## Cross-repo alignment (Iplanic contract — verified in review, not gate-resolved)

Iplanic's `iplan-canonical-json` is normative in the sibling `iplanic` repo
(`docs/standards/IPLAN-CANONICALIZATION.md`, decision D-0021): `canonical_hash =
lowercasehex(sha256(rfc8785.dumps(drop_null(value))))`; the signed
`execution-event` payload excludes `{signature, received_at}`; signatures are
`hmac-sha256` (raw-byte key) or `ed25519`, `value` lowercase hex. The reference
implementation is `iplan_canonical/` and the golden vectors this plan vendors are
`tests/contract/canonicalization/vectors/*.json` (canonical/`sha256` per vector;
`sig_hmac`/`sig_ed25519` carry the event, key, and expected value). Verified against
the `iplanic` repo this session (the IOPS-vs-Iplanic differential mismatch above was
run directly).

## Review log

> ≥2 passes before ready. ≥1 independent fresh-context (`Agent`). Final pass states
> zero findings.

### Pass 1 - 2026-06-11 - author

- Verified the 6 in-repo ledger citations by opening each file at the cited line.
- Ran the IOPS-vs-Iplanic differential: IOPS `sign_event` over `_canonical` does
  not reproduce Iplanic's golden `sig_hmac` value (`7ce5… ≠ bcac…`); confirmed the
  divergences (drop-null, `received_at` inclusion, raw-vs-utf8 key, JCS).
- Scoped narrowly: a new signer module + vendored-vector conformance; the standalone
  ledger signer is untouched, so existing security tests are unaffected.
- Open questions for independent pass: (a) does adopting JCS require any change to
  the standalone ledger's hash-chain (it must not)? (b) is vendoring the Iplanic
  vectors (vs a runtime dep on the `iplanic` repo) consistent with the IOPS
  no-upstream-dependency stance (D-0011/intake precedent)? (c) ed25519 key handling
  — does `cryptography` cover the seed/public-key forms the Iplanic vectors use?

### Pass 2 - 2026-06-11 - independent (paired with PLAN-013 re-grounding)

Fresh-context reviewer **ran the differentials in both repos** and confirmed the
two headline deliverables:

- **Divergence is real:** IOPS `_canonical` + `hmac(key_hex.encode())` → `7ce50f5e…`
  vs Iplanic `sign(signing_payload(event), 'hmac-sha256', bytes.fromhex(key_hex))`
  → `bcac738e…` (= the vector value). Every enumerated divergence is accurate and
  each is independently load-bearing (isolating `received_at` alone still
  mismatches). The raw-vs-utf8 key divergence is concrete — IOPS `signing_key` is a
  utf-8 `str` (`config.py:32`).
- **PLAN-014's spec reproduces all three vector families** byte-for-byte: `canon_*`
  + `normalize_omit_vs_null` (canonical bytes + sha256), `sig_hmac` (`bcac…`,
  raw-byte key, lowercase hex), and `sig_ed25519` (from the 32-byte seed; `verify`
  succeeds against the public hex). The spec matches `iplan_canonical/canonical.py`
  + `signing.py` field-for-field incl. `EXCLUDED_EVENT_FIELDS = ("signature",
  "received_at")`; `rfc8785>=0.1.4` + `cryptography>=42` are the correct libs.
- All citations (PLAN-013 rows 4/9; PLAN-014 rows 1–6) resolve; the cross-repo note
  matches the iplanic source; `D-0017` is the correct next id; the standalone
  `sign_event`/hash-chain ledger is correctly left unchanged (existing security
  tests unaffected).

**No BLOCKER, no load-bearing issues.** One minor doc fix folded in:

- PLAN-014 said `sign` returns the `{key_id, algorithm, value}` object, but the
  Iplanic reference `sign` returns a bare hex `value` (no `key_id` input). → Approach
  + Task 2 now state `sign` returns the hex `value`; the object is assembled by the
  consumer (`to_execution_events`, which PLAN-013 already has), and the HMAC raw-key-
  bytes convention is named explicitly.

**Result:** ready — no further findings.
