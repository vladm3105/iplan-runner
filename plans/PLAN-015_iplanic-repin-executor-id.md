# PLAN-015 — re-pin Iplanic mirrors to `1.3-draft`; conform to the `executor_id` hash form

> Iplanic shipped its first breaking change (PLAN-012 / D-0031): `executor_id` is
> tightened from a free string to `^exec:[a-z2-7]{16,}$`, and the schema set is
> bumped `1.2-draft → 1.3-draft` (commit `fb5f46d`). IOPS pins Iplanic's mirrors by
> commit, so its CI stays green until it deliberately re-pins — this plan is that
> coordinated lockstep follow-up. Advance the pin, rewrite IOPS's non-conforming
> `exec:remote` to the hash form, and **enforce** the pattern so IOPS rejects a
> payload Iplanic would reject. Record as **D-0018**.

## Scope

### A. Advance the pin (3 records)

The vendored mirror metadata moves from `bf3b9b6` / `1.2-draft` to `fb5f46d` /
`1.3-draft`:

- `framework/remote/iplanic-vectors/SOURCE.md` — the `Iplanic schema_version` and
  `Pinned commit` table rows.
- `framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml` header (`schema_version`,
  `pinned commit`).
- `framework/remote/EXECUTION-EVENT-TEMPLATE.yaml` header (same two).
- `docs/IPLAN-ECOSYSTEM.md` — the ecosystem comparison table cell that states the
  Iplanic `schema_version` (`1.2-draft → 1.3-draft`); else it goes stale.

**The vendored canonicalization vectors do not change.** Iplanic PLAN-012
**exempted** the canon goldens (`canon_event`, `sig_hmac`, `sig_ed25519` keep
`exec:abc` — opaque payload baked into the precomputed `canonical`+`sha256`), so the
IOPS copies remain byte-identical. The re-pin re-verifies byte-identity (the signing
conformance suite reproduces every value), it does not re-author the vectors.

### B. Rewrite IOPS's non-conforming `executor_id`

IOPS's own identity value is `exec:remote` — 6 chars, which fails
`^exec:[a-z2-7]{16,}$`. It is pure flow-through (carried from the task payload into
the manifest + emitted events), so one value change ripples to the golden expect and
the test assertions. Replace `exec:remote` with a conforming
`exec:<≥16 base32 a-z2-7>` (e.g. `exec:iopsremote2zqf7kx3a`) in:

- `framework/conformance/remote/accept/payload.yaml` (the input);
- `framework/conformance/remote/accept/expect.yaml` (six derived sites: manifest +
  events);
- `framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml` (the template example);
- both engines' `tests/test_remote.py` (the two `== "exec:remote"` assertions each).

**Regenerate the golden signatures.** `executor_id` is one of the `_IDENTITY_FIELDS`
that goes into the **signed** canonical payload (`events.py` `sign(signing_payload(
event))`), so changing it changes every event's `signature.value`. The conformance
test recomputes events live and asserts `events == expect["events"]`, so the **five**
golden `signature.value` fields in `expect.yaml` (lines 61, 82, 102, 122, 143) must
be **regenerated** from the rewritten payload — a stale value fails the accept
projection. This is a generated artifact: rewrite the `executor_id`, run the
projection, and capture the new signature values into `expect.yaml` (do not hand-edit
the hashes).

This makes IOPS's conformance data demonstrate an Iplanic-acceptable event.

### C. Enforce the hash form (the "tighten")

Conforming *test data* is not conforming *behavior*: at runtime IOPS would still
carry a malformed `executor_id` straight through. Add a validation rule so a payload
whose `executor_id` is present but does not match `^exec:[a-z2-7]{16,}$` is rejected
**before** events are emitted. Mirror across both engines (D-0011 byte-identical):

- `validation/payload_rules.py` (both): a compiled `^exec:[a-z2-7]{16,}$` constant +
  a check that appends `REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT` when `executor_id` is
  present but non-conforming (presence itself stays `REMOTE.PAYLOAD_IDS_MISSING`).
- `validation/_base.py` SEVERITY (both): `REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT: error`.
- `framework/conformance/rule-ids.yaml`: the new rule under `REMOTE-001`.
- `framework/conformance/remote/reject_executor_id/` — a new vector mirroring
  `reject_context`: `payload.yaml` valid except `executor_id` (e.g. `exec:bad`),
  `expect.yaml` → `rule_ids: [REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT]`. The rule-coverage
  test auto-scans `remote/**/expect.yaml`, so catalog ↔ vector parity holds both ways.

### D. Contract doc + versions + decision

- `framework/remote/REMOTE_EXECUTOR_CONTRACT.md`: note the `executor_id` hash form
  (`^exec:[a-z2-7]{16,}$`, Iplanic §2.1) and the `1.3-draft` pin.
- Bump the framework contract MINOR (additive rule): `framework/VERSION` and
  `EXECUTION_REGISTRY.yaml` `spec_version` `1.1.0 → 1.2.0`, and **both** engine
  marker files `platforms/hermes/FRAMEWORK_SPEC_VERSION` +
  `platforms/claude/FRAMEWORK_SPEC_VERSION` `1.1.0 → 1.2.0` — these three are
  **parity-gated** (`tests/conformance/test_registry.py` `spec_version ==
  framework_version`; `tests/conformance/test_engines.py` each marker ==
  `framework_version`), so a missed carrier fails CI. Also bump both engine
  `__version__` `0.12.0 → 0.13.0` (not parity-tested, but kept in step).
- Record **D-0018** in `plans/DECISIONS.md` (newest-first, above D-0017).

**Out of scope:** the byte-level `iplan-canonical-json` signing (unchanged by
PLAN-012); the vendored canon-vector contents (exempt, byte-identical); any Iplanic
repo change.

## Decision (D-0018)

**Re-pin to Iplanic `1.3-draft` / `fb5f46d` and conform to the `executor_id` hash
form, enforcing it with a new `REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT` rule.** Enforcement
(not just conforming test data) is included because IOPS carries `executor_id`
through to emitted events; without the rule a malformed id would be emitted and
rejected downstream by Iplanic ingestion. The canon vectors stay byte-identical
(Iplanic exempted them), so the signing contract is untouched. Additive rule →
framework `MINOR` bump.

## Tasks

1. Bump the three pin records (A) to `fb5f46d` / `1.3-draft`.
2. Re-verify the vendored canon vectors are byte-identical to Iplanic@`fb5f46d`
   (`git -C ../iplanic show fb5f46d:tests/contract/canonicalization/vectors/...`),
   then run the signing conformance suite — it must still reproduce every value.
3. Rewrite `exec:remote → exec:iopsremote2zqf7kx3a` across the four files (B), then
   **regenerate** the five `expect.yaml` golden `signature.value`s from the rewritten
   payload (run the projection, capture the output — do not hand-edit hashes); rerun
   the remote conformance suite (manifest/events incl. signatures match the golden).
4. Add the `REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT` rule (C) across both engines + catalog
   + the new `reject_executor_id` vector.
5. Update `REMOTE_EXECUTOR_CONTRACT.md` (D); bump the versions; record D-0018.
6. Run `python -m unittest discover -s tests/conformance` + per-engine
   `pytest platforms/<engine>` + `mypy --strict` green; `pre-commit run --all-files`.

## Verification

- Conformance: `tests/conformance` green — the accept projection matches the
  updated golden cross-engine; the new `reject_executor_id` vector emits exactly
  `REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT`; `test_rule_catalog` parity holds (catalog ↔
  vectors, both directions); the signing vectors still reproduce byte-for-byte.
- Negative: a payload with `executor_id: "exec:remote"` (old form) now **fails**
  validation with `REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT`; a conforming id passes.
- Both engines byte-identical (the cross-engine conformance asserts agreement).
- The five `expect.yaml` `signature.value`s differ from the pre-rewrite goldens
  (proof the signatures were regenerated, not left stale).
- `grep -rn 'exec:remote' .` returns nothing; `grep -rn 'bf3b9b6' framework/ docs/`
  and `grep -rn '1.2-draft' framework/remote/ docs/IPLAN-ECOSYSTEM.md` return nothing.
- `mypy --strict platforms/hermes/src platforms/claude/src` clean; `pre-commit` clean.

## Claim ledger

> Every load-bearing claim cites the `file:line` actually read. All in IOPS repo.
> Iplanic (cross-repo) facts — the `1.3-draft`/`fb5f46d` pin, the exempt canon
> vectors — are prose; the gate cannot resolve them.

| #   | Claim | Symbol | Citation |
| --- | ----- | ------ | -------- |
| 1   | the vendored mirror pins Iplanic `1.2-draft` (the row to bump to `1.3-draft`) | `1.2-draft` | framework/remote/iplanic-vectors/SOURCE.md:12 |
| 2   | the vendored mirror pins commit `bf3b9b6` (the row to bump to `fb5f46d`) | `bf3b9b6` | framework/remote/iplanic-vectors/SOURCE.md:13 |
| 3   | re-pin procedure is "re-copy and bump the commit; drift surfaces as a failing conformance vector" | `Re-pin` | framework/remote/iplanic-vectors/SOURCE.md:16 |
| 4   | the task-payload template header records `schema_version: 1.2-draft` + `pinned commit: bf3b9b6` | `pinned commit` | framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml:6 |
| 5   | the execution-event template header records the same pin pair | `pinned commit` | framework/remote/EXECUTION-EVENT-TEMPLATE.yaml:6 |
| 6   | IOPS's `executor_id` value is `exec:remote` — 6 chars, fails `^exec:[a-z2-7]{16,}$` | `exec:remote` | framework/conformance/remote/accept/payload.yaml:8 |
| 7   | the template example carries the same non-conforming `exec:remote` | `exec:remote` | framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml:21 |
| 8   | the golden expect derives `executor_id: exec:remote` (first of six sites — manifest + events) | `exec:remote` | framework/conformance/remote/accept/expect.yaml:33 |
| 9   | each engine's remote test asserts `manifest[...]["executor_id"] == "exec:remote"` | `exec:remote` | platforms/hermes/tests/test_remote.py:33 |
| 10  | each engine's remote test asserts every emitted event's `executor_id == "exec:remote"` | `exec:remote` | platforms/hermes/tests/test_remote.py:48 |
| 11  | the claude engine carries the identical assertions (dual-engine, D-0011) | `exec:remote` | platforms/claude/tests/test_remote.py:33 |
| 12  | `validate_payload` is where REMOTE rules are emitted; `executor_id` is a `_REQUIRED_IDS` presence check today (no format check) | `_REQUIRED_IDS` | platforms/hermes/src/iops_hermes/validation/payload_rules.py:13 |
| 13  | REMOTE findings are appended via `finding("REMOTE.PAYLOAD_…")` (the call shape the new rule mirrors) | `REMOTE.PAYLOAD_IDS_MISSING` | platforms/hermes/src/iops_hermes/validation/payload_rules.py:20 |
| 14  | each engine's SEVERITY dict lists the REMOTE rules (where the new rule's severity is added) | `REMOTE.PAYLOAD_IDS_MISSING` | platforms/hermes/src/iops_hermes/validation/_base.py:45 |
| 15  | the rule catalog declares the REMOTE-001 rules (where the new rule is registered) | `REMOTE-001` | framework/conformance/rule-ids.yaml:166 |
| 16  | the rule-coverage test auto-scans `remote/**/expect.yaml`, so a new reject vector's `rule_id` is covered both ways | `conformance" / "remote` | tests/conformance/test_rule_catalog.py:33 |
| 17  | the reject-vector shape is `payload.yaml` + `expect.yaml` with a sorted `rule_ids` list (the shape `reject_executor_id` mirrors) | `rule_ids` | framework/conformance/remote/reject_context/expect.yaml:1 |
| 18  | the remote conformance test compares the accept manifest against the golden `expect["manifest"]` (so the value rewrite must update both) | `expect["manifest"]` | tests/conformance/test_remote.py:64 |
| 18b | `executor_id` is a signed `_IDENTITY_FIELDS` member; `sign(signing_payload(event))` covers it, so rewriting it changes every `signature.value` | `signing_payload` | platforms/hermes/src/iops_hermes/ledger/events.py:63 |
| 18c | the golden `expect.yaml` carries precomputed `signature.value`s (the five to regenerate, first at this line) | `value` | framework/conformance/remote/accept/expect.yaml:61 |
| 19b | both engines carry a parity-gated `FRAMEWORK_SPEC_VERSION` marker (= `framework_version`) — a version carrier the bump must move | `framework_version` | tests/conformance/test_engines.py:15 |
| 19  | the framework registry `spec_version` is `1.1.0` and must equal `framework/VERSION` (the bump pair) | `spec_version` | framework/registry/EXECUTION_REGISTRY.yaml:9 |
| 20  | each engine `__version__` is `0.12.0` (bump to `0.13.0`) | `__version__` | platforms/hermes/src/iops_hermes/__init__.py:6 |
| 21  | the latest decision is D-0017 (so this is D-0018), newest-first ordering | `D-0017` | plans/DECISIONS.md:155 |
| 22  | the `remote_execution` block carries `executor_id` as the Iplanic identity for event emission (why the format must conform) | `executor_id` | framework/remote/REMOTE_EXECUTOR_CONTRACT.md:33 |

## Review log

> ≥2 passes before ready. ≥1 independent fresh-context (`Agent`). Final pass states
> zero findings.

### Pass 1 - 2026-06-11 - author

- Verified all 22 ledger citations by opening each file at the cited line.
- Confirmed the breakage is pure flow-through: `executor_id` moves payload →
  manifest/events verbatim, so one value rewrite ripples to the six `expect.yaml`
  sites + the four per-engine assertions; no projection logic changes.
- Confirmed the canon vectors are byte-identical to Iplanic's (PLAN-012 exempted
  them), so the re-pin is metadata + a re-verify, not a vector re-author — the
  signing contract is untouched.
- Confirmed the rule-coverage test scans `remote/**/expect.yaml`, so adding the rule
  to the catalog *requires* the new `reject_executor_id` vector (and vice versa) —
  Task 4's pieces are inseparable.
- Open questions for the independent pass: (a) is the format rule in-scope for a
  "re-pin", or should it be a separate hardening plan (the migration note says
  "tighten")? (b) is a framework `MINOR` bump correct for an additive rule, and which
  files carry `FRAMEWORK_SPEC_VERSION` that a parity test checks? (c) does any other
  IOPS payload/vector/fixture (beyond the five `exec:remote` files) carry a
  non-conforming `executor_id` the plan misses? (d) should the format rule fire only
  when `executor_id` is present (avoiding a double-finding with
  `REMOTE.PAYLOAD_IDS_MISSING` when it is absent)?

### Pass 2 - 2026-06-11 - independent

Fresh-context reviewer (`Agent`) verified empirically — opened every citation, swept
the whole repo for `executor_id` values, `diff`ed the vendored canon vectors against
Iplanic@`fb5f46d`, and **recomputed an event HMAC** to test the signature claim.

- **All 22 ledger citations accurate**; dual-engine mirror (D-0011) confirmed
  byte-identical for `payload_rules.py`/`_base.py`/`events.py` (tests differ only in
  the import package name).
- **executor_id sweep complete**: the only non-conforming value is `exec:remote`
  (the five files named) plus the exempt `exec:abc` in the vendored canon vectors;
  `cli/commands.py`/`intake/payload.py`/`ledger/events.py` reference it as a key, not
  a value. No missed value.
- **Canon vectors confirmed byte-identical** to Iplanic@`fb5f46d` (`exec:abc` exempt,
  per D-0031) — the re-pin is metadata + re-verify, not a re-author.
- **Double-finding design correct**: an absent `executor_id` fires only
  `PAYLOAD_IDS_MISSING` (`not payload.get(...)`); a present-but-malformed one fires
  only the new format rule. **Reject-vector coupling** holds both ways.
- **Scope judged sound**: A+B alone would conform IOPS's *data* while runtime still
  emits a malformed signed `executor_id` Iplanic rejects; the rule (C) is the real
  conformance. Keep bundled.

**One LOAD-BEARING finding — fixed:**

- **Golden signature regeneration was missing.** `executor_id` is in the *signed*
  canonical payload, so rewriting it changes all five `signature.value`s; the
  conformance test recomputes events live and compares to the golden, so stale
  signatures fail `test_accept_projection_matches_golden`. The reviewer proved it
  (HMAC of the new id ≠ the stored golden). → Scope B, Task 3, verification, and
  ledger rows 18b/18c now require **regenerating** the five `expect.yaml` signature
  values from the rewritten payload (capture from the projection, don't hand-edit).

Minor, folded in:

- `docs/IPLAN-ECOSYSTEM.md:42` states the Iplanic `schema_version` (`1.2-draft`) —
  added to the pin records (Scope A) + the verification grep, else it goes stale.
- Named the two parity-gated `FRAMEWORK_SPEC_VERSION` marker files +
  `test_registry`/`test_engines` explicitly (Scope D, ledger row 19b) instead of
  hand-waving "any carrier".

**No remaining load-bearing findings.**

**Result:** ready — no further findings.
