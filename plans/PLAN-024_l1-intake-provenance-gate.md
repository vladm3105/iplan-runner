# PLAN-024 — L1 intake-provenance gate (cross-repo, end-to-end) (D-0024)

**Status: READY (prepared read-only) — AI recommendation: DEFER (not urgent), build A-first if pursued.**
The plan is verified (23 cited claims across 3 repos, independent review = zero load-bearing) and correct.
But the runner-side gate (C) is **defense-in-depth that is largely covered today**: iplanic already
verifies initiator provenance at **import** (D-0110: a plan below the floor never becomes approvable, so it
is never dispatched), and the runner already **authenticates the dispatcher** via the `IOPS_RECEIVER_TOKEN`
bearer. The runner gate adds value mainly under (a) **multiple/untrusted dispatchers** or (b) **independent
third-party auditability** of the runner — neither a current need (single dispatcher, mutual trust). Cost is
high (a 3-repo, ratification-gated change, both engines). **Founder call (this is cross-repo):** if pursued,
sequence **A → B → C** (never C alone — nothing to verify until A+B deliver the envelope); C is un-buildable
and un-testable until then.
**Decision:** D-0024 (prepared; not scheduled) · **Layer:** consumer enforcement (IPLAN Assurance L1) · **Date:** 2026-07-04

> **Founder-executed / cross-repo:** *prepared* by the AI (read-only); the founder reviews, implements,
> and runs all git operations. Rows marked `[std]` resolve with
> `check_plan --root /opt/data/aidoc-flow/iplan-standard`; rows marked `[iplanic]` with
> `--root /opt/data/aidoc-flow/iplanic`. Gate: `python .claude/skills/verified-planning/check_plan.py
> plans/PLAN-024_l1-intake-provenance-gate.md --root /opt/data/aidoc-flow/iplan-standard --root /opt/data/aidoc-flow/iplanic`.

## Problem

IPLAN Assurance **L1** requires a *consumer* to verify the initiator's signed `intake_control.provenance`
envelope **at intake, before execution**, and **refuse to execute** on failure (IPLAN-ASSURANCE §2).
iplan-runner is named as such a consumer (§8/§9). But it **cannot** verify anything today: the dispatched
payload it receives is a `task.schema.json` (fields `iplan_id`, `plan_version_id`, `work_order`,
`context_package`, …) that carries **no `intake_control.provenance`** and **not the signed IPLAN document**;
the `intake_control` the runner *does* have is **synthesized locally** with `"approved": True` **hardcoded**
(`intake/payload.py:67`). So there is nothing signed for the runner to check.

**This is therefore a cross-repo program, not a runner-only slice** — sequenced A → B → C:

| Slice | Repo | Change | Depends on |
| --- | --- | --- | --- |
| **A** | iplan-standard | additive `provenance` (+ the signed canonical surface) on `task.schema.json` | — |
| **B** | iplanic (dispatcher) | thread the L1-verified `intake_control.provenance` into the dispatched task payload | A |
| **C** | **iplan-runner** | verify at intake — the gate (keyring + `INTAKE.PROVENANCE_*` at `loop.py:332`, **both engines**) | A, B |

A + B are **separate plans in their own repos** (iplan-standard + iplanic); this plan **sequences the whole
program and fully designs C** (the runner gate, the piece that was asked for). C is not buildable or even
testable until A + B deliver the envelope.

**Ratification gate:** IPLAN-ASSURANCE is **DRAFT / non-normative** (§9 "Remaining before ratification").
Slice A (a normative schema change) should land through the standard's CHG/GATE-SPEC, and iplan-runner
re-pins the vendored standard after — no runner build begins until A ratifies + B ships.

## Slice A — iplan-standard: deliver the envelope on the task payload

The verifier needs two things the task payload lacks: (1) the **`intake_control.provenance`** envelope
`{initiator_key_id, algorithm, value, signed_at}` (defined today only on the *document*,
`iplan-document.schema.json:60` `[std]`), and (2) the **signed canonical surface** it covers — the IPLAN
canonicalized with `intake_control` excluded (IPLAN-ASSURANCE §2 "Signed payload", `IPLAN-ASSURANCE.md:58`
`[std]`). Two shapes (a design decision for slice A):

- **A1 (whole signed document):** add the full `iplan-document` (or its `intake_control.provenance` + the
  document body) to `task.schema.json`, so the consumer recomputes `provenance_signing_payload(document)`
  itself (the reference algorithm, `test_provenance.py:36` `[std]`). Faithful; larger payload.
- **A2 (envelope + digest):** add `provenance` + the precomputed canonical-signed-payload **digest** the
  signature covers. Smaller; but the consumer trusts the dispatcher's canonicalization rather than
  recomputing it — weaker (it no longer independently binds the document content). **A1 recommended** (the
  consumer must independently canonicalize to *mean* anything; §2 step 1 is "canonicalize").

Slice A adds the field **additively** (L0 omits it, `iplan-document.schema.json` provenance is optional),
re-derives the runner's consumed subset `framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml` (which carries
**no** provenance today — 0 matches), and ships accept/reject golden vectors (extending
`tests/contract/provenance/vectors/` `[std]`). **Open (A):** the standard's current provenance vectors
verify only the *signature* — they do **not** exercise the §2-step-3 scope check (initiator authorized for
the plan's `client_id`/`project_id` scope, `IPLAN-ASSURANCE.md:84` `[std]`), so slice A must add
scope-authorization vectors for C to enforce it.

## Slice B — iplanic: dispatch the provenance

iplanic already **verifies and holds** the initiator provenance: `import_pipeline.import_iplan` runs
`verify_provenance` at L1 import (`iplanic_service/management/import_pipeline.py:93` `[iplanic]`), so the
approved version carries a verified `intake_control.provenance`. Slice B threads that envelope (+ the
signed canonical surface per A1) into the dispatched task at
`iplanic_service/orchestrator/dispatch_payload.py:44` `build_task_payload` `[iplanic]` — the single place a
plan step becomes a `task.schema.json` payload. Gated by iplanic's existing assurance posture
(`IPLANIC_ASSURANCE_MIN_ACCEPT`); at L0 the field is omitted (backward-compatible). Depends on A (the
schema field must exist first).

## Slice C — iplan-runner: verify at intake (THE GATE — the focus of this plan)

Once A + B deliver `intake_control.provenance` on the task payload, the runner enforces it. **Built in
BOTH engines** (`platforms/claude` + `platforms/hermes`, strict isolation D-0011, `CLAUDE.md:56`).

### C1. Initiator keyring (config)

A new **authorized-initiator keyring** — the §9 R1 baseline (a signed allowlist `initiator_key_id →
{algorithm, public_key|secret}`). Provisioned via a new env/config field on `Config` (`config.py:21`,
beside the receiver fields e.g. `receiver_key_id` `config.py:43`) and threaded into `ReceiverDeps`
(`receiver/service.py:33`, which already carries `key`/`key_id` `receiver/service.py:40`). No new crypto —
resolution reuses the vendored verifier.

### C2. `verify_provenance` (reuse the vendored signer)

Mirror the standard's reference exactly: `provenance_signing_payload(document) =
drop_null({k: v for k, v in document.items() if k != "intake_control"})` then
`verify(provenance_signing_payload(document), envelope["value"], algorithm=envelope["algorithm"],
key=<resolved>)` — the payload is passed **directly** (not wrapped in a `{"canonical_hash": …}` object;
that wrapper is the evidence-seal pattern, not provenance). Reuses the **already vendored**
`iplan_canonical.signing.verify` (`security/iplan_canonical/signing.py:52`, re-exported via
`security/iplanic_signing.py:15`). The reference to copy is `test_provenance.py:36` / `:43` `[std]`
(`provenance_signing_payload` / `verify_provenance`). No new dependency.

### C3. `INTAKE.PROVENANCE_*` rules composed at the intake choke point

Add the four findings from IPLAN-ASSURANCE §2 (`IPLAN-ASSURANCE.md:81` `[std]`) — `INTAKE.PROVENANCE_UNSIGNED`
/ `_BAD_SIGNATURE` / `_UNKNOWN_INITIATOR` / `_UNAUTHORIZED_INITIATOR` — to `validation/intake_rules.py`'s
`validate_intake` (`validation/intake_rules.py:13`), **composing with, not replacing, INTAKE-001**. They
emit `Finding`s via the `finding(rule_id, message)` helper (`validation/_base.py:60`); each new rule id is
added to the `SEVERITY` map (`validation/_base.py:12`) **and** the canonical catalog
`framework/conformance/rule-ids.yaml` (the conformance suite asserts parity). Enforcement is the existing
single choke point: `loop.py:332` `if status_of(validate_intake(manifest)) == "fail": raise` — a
`fail`-severity provenance finding **refuses execution** (§2), before `_init_ledger`/`_drive`.

### C4. Assurance floor + scope authorization

- **Floor:** a config level (`L0|L1`, mirroring iplanic's `IPLANIC_ASSURANCE_MIN_ACCEPT`); default **L0**
  keeps current behavior byte-for-byte (no envelope required — backward-compatible); **L1** makes a missing
  envelope `INTAKE.PROVENANCE_UNSIGNED` = `fail`.
- **Scope (§2 step 3, `IPLAN-ASSURANCE.md:75` `[std]`):** confirm the resolved initiator is authorized for
  the task's `org_id`/`project_id`. **Depends on slice A adding scope vectors** (none exist today) — until
  then C3 can ship signature-only and `_UNAUTHORIZED_INITIATOR` is a named follow-on.

### C5. The local-`intake_control` reconciliation (load-bearing)

The runner synthesizes `intake_control` with `approved: True` hardcoded (`intake/payload.py:67`). Once the
payload carries a real `intake_control.provenance`, `_build_manifest` (`intake/payload.py:48`) must carry
**both** through to the manifest so `validate_intake` can verify: (1) the received `provenance` envelope,
**and (2) the full delivered document body** (per slice A1) — because `INTAKE.PROVENANCE_BAD_SIGNATURE`
requires the rule to recompute `provenance_signing_payload(document)`, so the document (minus its
`intake_control`), not just the envelope, must reach the rule. The `approved`/`exec_ready_score` synthesis
stays (iplanic's dispatch assertion); provenance is **added alongside**, not replacing it.

## Out of scope / prerequisites (named)

- **Slices A + B are separate plans** (iplan-standard `PLAN-…` + iplanic `PLAN-…`); this plan sequences
  them. A ratifies through the standard's CHG/GATE-SPEC; the runner re-pins after (per PLAN-023).
- The **Sigstore/IdP** keyring direction (§9 R1 "additive later"); the L2 transparency-log consumer contract
  (separate). No runner build begins before A ratifies + B ships (nothing to verify until then).

## Tests (slice C, once A+B land)

Both engines, from the standard's golden vectors (`tests/contract/provenance/vectors/*` `[std]`):
accept (ed25519 + hmac) → no `INTAKE.PROVENANCE_*` finding, execution proceeds; reject (tampered) →
`_BAD_SIGNATURE` = `fail` → `loop.py:332` raises → **no execution**; unsigned under floor L1 → `_UNSIGNED`
= `fail`; unknown `initiator_key_id` → `_UNKNOWN_INITIATOR`; floor L0 + no envelope → **passes** (backward
compat); the `rule-ids.yaml`↔`SEVERITY` parity conformance test stays green. Scope-authz tests gated on the
slice-A vectors.

## Claim ledger

| #   | Claim | Symbol | Citation |
| --- | ----- | ------ | -------- |
| 1 | The runner synthesizes `intake_control` locally with `"approved": True` **hardcoded** (no received provenance) | `approved` | platforms/claude/src/iplan_claude/intake/payload.py:67 |
| 2 | `_build_manifest` is where the manifest `intake_control` is constructed — must carry a received envelope through | `_build_manifest` | platforms/claude/src/iplan_claude/intake/payload.py:48 |
| 3 | The single intake choke point: `if status_of(validate_intake(manifest)) == "fail": raise` — where a `fail` provenance finding refuses execution | `validate_intake` | platforms/claude/src/iplan_claude/orchestrator/loop.py:332 |
| 4 | `validate_intake` (the INTAKE-001 category) — where `INTAKE.PROVENANCE_*` compose | `validate_intake` | platforms/claude/src/iplan_claude/validation/intake_rules.py:13 |
| 5 | `finding(rule_id, message)` emits a `Finding` looking up `SEVERITY[rule_id]` — new rule ids must be added to the map | `finding` | platforms/claude/src/iplan_claude/validation/_base.py:60 |
| 6 | The `SEVERITY` map — each `INTAKE.PROVENANCE_*` id added here (and the canonical catalog) | `SEVERITY` | platforms/claude/src/iplan_claude/validation/_base.py:12 |
| 7 | `status_of(findings)` → `pass/warn/fail` — the fail that raises at the choke point | `status_of` | platforms/claude/src/iplan_claude/validation/_base.py:64 |
| 8 | `verify(payload, value, *, algorithm, key)` — the **already vendored** verifier the gate reuses (no new crypto) | `def verify` | platforms/claude/src/iplan_claude/security/iplan_canonical/signing.py:52 |
| 9 | `security/iplanic_signing.py` re-exports the vendored `canonicalize`/`verify`/`drop_null` — the runner's stable import surface | `canonicalize` | platforms/claude/src/iplan_claude/security/iplanic_signing.py:15 |
| 10 | `Config` — where the initiator-keyring config field is added (beside `receiver_key_id`) | `class Config` | platforms/claude/src/iplan_claude/config.py:21 |
| 11 | `ReceiverDeps` already carries `key`/`key_id` — the keyring dep is threaded here | `class ReceiverDeps` | platforms/claude/src/iplan_claude/receiver/service.py:33 |
| 12 | The consumed task-payload subset has `context_package` etc. but **no** provenance today — the delivery gap slice A closes | `context_package` | framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml:31 |
| 13 | Strict per-engine isolation (D-0011) — the gate is built in BOTH `claude` + `hermes` | `isolation` | CLAUDE.md:56 |
| 14 | The canonical rule catalog (`INTAKE-001` present) — `INTAKE.PROVENANCE_*` ids added here in parity with each engine's `SEVERITY` | `INTAKE-001` | framework/conformance/rule-ids.yaml:19 |
| 15 | `[std]` L1 consumer contract: the **signed payload** = the IPLAN canonicalized with `intake_control` excluded | `Signed payload` | docs/standards/IPLAN-ASSURANCE.md:58 |
| 16 | `[std]` the detached envelope at `intake_control.provenance` | `Envelope` | docs/standards/IPLAN-ASSURANCE.md:64 |
| 17 | `[std]` verify at intake, **refuse to execute** on failure (incl. the §2-step-3 scope check) | `refuse to execute` | docs/standards/IPLAN-ASSURANCE.md:75 |
| 18 | `[std]` the proposed `INTAKE.PROVENANCE` rule category (the four findings) | `INTAKE.PROVENANCE` | docs/standards/IPLAN-ASSURANCE.md:81 |
| 19 | `[std]` reference `provenance_signing_payload(document)` = drop-null(document minus `intake_control`) — the exact algorithm C2 mirrors | `provenance_signing_payload` | tests/contract/test_provenance.py:36 |
| 20 | `[std]` reference `verify_provenance(document, keyring)` — resolve `initiator_key_id` + verify | `verify_provenance` | tests/contract/test_provenance.py:43 |
| 21 | `[std]` the `provenance` envelope is defined on the **document** schema (not the task) — the field slice A must add to `task.schema.json` | `provenance` | schemas/iplan-document.schema.json:60 |
| 22 | `[iplanic]` `build_task_payload` maps a plan step → `task.schema.json` — the slice-B hook that must include the envelope | `build_task_payload` | iplanic_service/orchestrator/dispatch_payload.py:44 |
| 23 | `[iplanic]` iplanic already verifies + holds the provenance at import (`verify_provenance` in `import_iplan`) — the source of the envelope slice B dispatches | `verify_provenance` | iplanic_service/management/import_pipeline.py:93 |

## Review log

### Pass 1 - 2026-07-04 - author self-review (prepared read-only)

- **The headline finding: not a runner-only slice.** Recon proved the runner receives `task.schema.json`
  with no `intake_control.provenance` and synthesizes `intake_control` (`approved:True` hardcoded,
  `payload.py:67`). The gate is blocked on upstream delivery (A: standard schema, B: iplanic dispatch). This
  plan sequences A→B→C and details C. Flagged for the reviewer to confirm the gap (grep `provenance` in
  `task.schema.json` / the runner template).
- **Reuse, not new crypto:** verify + canonicalize are already vendored (`iplan_canonical`, PLAN-023); the
  reference `provenance_signing_payload`/`verify_provenance` is copy-ready from the standard's contract test.
- **Both engines (D-0011)** — C is implemented twice; `rule-ids.yaml` + each `SEVERITY` map updated in
  lockstep (conformance asserts parity).
- **Scope-authz (§2 step 3) is under-specified upstream** — no golden vectors exist; slice A must add them,
  else C ships signature-only with `_UNAUTHORIZED_INITIATOR` a named follow-on. Confirm this is the honest
  boundary.
- **A1 vs A2 (whole document vs envelope+digest):** recommended A1 so the consumer independently
  canonicalizes (§2 step 1) — A2 would make the consumer trust the dispatcher's canonicalization. Open for
  the reviewer.

### Pass 2 - 2026-07-04 - independent (fresh-context `code-reviewer` agent, cross-repo)

**Zero load-bearing findings.** All 23 ledger rows verified against the correct repo (the reviewer re-ran
`check_plan` across all three `--root`s — all citations resolve). **The headline cross-repo claim is
rigorously true:** `iplan-standard/schemas/task.schema.json` has **no** `provenance`/`intake_control` (zero
grep matches); the envelope is on `iplan-document.schema.json:60` (the document, not the task); the runner
hardcodes `approved: True` (`payload.py:67`) and the consumed template carries no provenance — so A→B→C is
real, not manufactured. **Slice B is feasible** (not aspirational): `import_pipeline` persists the **full
document** (incl. `intake_control.provenance`) via `content_store.put`, so `build_task_payload` can retrieve
and thread the envelope. **Both engines confirmed** (hermes mirror has identical hooks at identical lines).
**A1-vs-A2 sound** (A1 lets the consumer independently canonicalize — required for the security property).
**Ratification gate + scope-authz gap honestly flagged** (the standard is DRAFT; provenance vectors are
signature-only, no unauthorized-scope vector).

**Four minor findings, all folded:** (1) C2 pseudocode — the payload is passed to `verify` **directly**,
not wrapped in `{"canonical_hash": …}` (the evidence-seal pattern); corrected to match
`test_provenance.py:43`. (2) C5 now states explicitly that the **full delivered document body** (per A1),
not just the envelope, must reach `validate_intake` (BAD_SIGNATURE recomputes
`provenance_signing_payload(document)`). (3) `authorized_scopes` reworded to the standard's "the plan's
`client_id`/`project_id` scope". (4) row-line trivia (non-blocking). No MD056 risk (the only `|` code span,
`L0|L1`, is in prose, not a table row).

**Result:** ready — no load-bearing findings. **(Prepared read-only; AI recommendation = DEFER, build
A-first — see the Status header. Founder owns the cross-repo call + all git operations.)**
