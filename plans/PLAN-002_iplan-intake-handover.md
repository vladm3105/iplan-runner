# IPLAN Intake, Ingestion & Handover Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** Build the execution engine's **front door and back door** (Roadmap
Phase 2 → `v0.2.0`): consume an **approved** SDD IPLAN at the `EXEC-Ready ≥90`
boundary, normalize it into a validated **intake manifest** (the task graph the
orchestrator will consume), and define the **handover receipt** published back
toward the control plane when a ledger completes.

**Architecture:** Additive to the Phase-1 contract, under the structure
conventions (D-0014). Two new engine-agnostic concern-dirs (`framework/intake/`,
`framework/handover/`) with templates + rules + golden vectors; each engine
(`hermes`, `claude`) gets its own `intake/`, `handover/`, validators, and a thin
`config.py`, kept identical by golden vectors (D-0012) + a new reader-parity
check. Strict isolation (D-0011) holds — no shared code, no dependency on the
SDD repo.

**Tech Stack:** YAML contract + vectors; Python ≥3.11; `pytest` (per-engine);
`unittest` conformance; `ruff` + `mypy --strict`.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-002 |
| Depends on | `PLAN-001` (DONE); `plans/DECISIONS.md` D-0011..D-0014; Roadmap Phase 2 |
| Status     | DONE - 2026-05-24 |
| Feeds      | `PLAN-003` (run loop consumes the intake manifest); `PLAN-006` (handover ↔ landing) |

## Objective

Today the engine can only `read_iplan_ref` (id/version/checksum). It cannot
discover *what to execute*, verify the plan was *approved*, or report a result
*back*. Phase 2 closes the boundary with SDD:

1. **Intake (front door).** Read an approved SDD IPLAN file and **normalize** it
   (via a documented, tolerant, configurable field mapping — **no hard
   dependency on the SDD repo**) into an `iplan-intake` manifest: source
   identity + checksum, the `EXEC-Ready` approval signal, the isolation scope,
   and the **task graph** (tasks, dependencies, acceptance).
2. **Ingestion validation.** Validate the manifest (approval ≥ 90, scope
   present, tasks well-formed, dependencies resolvable) — a pure, deterministic
   validator emitting catalog rule IDs.
3. **Handover (back door).** Define an `iplan-handover-receipt` that binds a
   completed ledger + its gate verdict + audit report into a result published
   toward the control plane, plus its validator.
4. **Thin config seam.** A minimal per-engine `config.py` (intake field mapping,
   ids, paths) that later phases extend.

This stays in the **stateless / golden-vector** regime — no orchestration yet
(that is Phase 3). The intake manifest is the clean, validated hand-off the run
loop will consume.

## Scope

**In:**

1. `framework/intake/` — `IPLAN-INTAKE-TEMPLATE.yaml` (`iplan-intake`) +
   `INTAKE_CONTRACT.md` (consumed-subset spec, approval rule, SDD→manifest field
   mapping, the `EXEC_READY_MIN = 90` threshold).
2. `framework/handover/` — `IPLAN-HANDOVER-RECEIPT-TEMPLATE.yaml`
   (`iplan-handover-receipt`) + `HANDOVER_CONTRACT.md`.
3. Rule-ID catalog additions: `INTAKE-001` (7 rules) + `HANDOVER-001` (4 rules);
   `RULE-IDS.md` + registry updated.
4. Golden vectors for both new document types (valid baseline + one per rule);
   **reader-parity samples** (SDD-IPLAN-shaped input → normalized manifest).
5. Per engine (`hermes`, `claude`, independent copies): `intake/reader.py`
   (`ingest_iplan`), `config.py`, `validation/intake_rules.py`,
   `validation/handover_rules.py`, `handover/receipt.py`
   (`build_handover_receipt`, injected clock); `engine.py` dispatch + adapter
   methods (`ingest_iplan`, `build_handover`); `cli.py` `intake` + `handover`
   commands; tests.
6. Conformance: new vectors auto-discovered; a new `test_intake_readers.py`
   (cross-engine **reader parity** on produced manifests); spec-version bump to
   `0.2.0` across `framework/VERSION`, registry, both engines.

**Out:**

1. Orchestration / run loop / task state transitions (Phase 3 / `PLAN-003`).
2. Actually executing tasks, applying edits, or running evidence (Phase 4).
3. Live publishing of the handover receipt to an external system — we *produce
   and validate* the receipt; transport/landing is Phase 6.
4. Full config contract + secrets (Phase 8); only a thin seam here.
5. Authn/authz or signing of intake/handover docs (Phase 7).
6. Parsing every SDD IPLAN field — only the subset this framework consumes.

## Approach

**Normalize, don't couple (no SDD dependency).** SDD's IPLAN schema lives in
another repo and evolves independently. Rather than import or hard-code it, each
engine's `ingest_iplan` maps an SDD-IPLAN-shaped document into our own
`iplan-intake` manifest using a **configurable field mapping** (defaults
documented in `INTAKE_CONTRACT.md`, overridable via `config.py`). The manifest
is the stable seam; SDD schema drift is absorbed by the mapping, not the engine
core.

**Two stateless artifacts → golden vectors.** Both `iplan-intake` and
`iplan-handover-receipt` are documents validated by pure functions, so they slot
straight into the Phase-1 conformance machinery (`validate(document) →
{status, findings}`, replayed against every engine). No scenario vectors needed
until Phase 3.

**Reader parity is a new, deterministic dimension.** `ingest_iplan` is a pure
transform `SDD-IPLAN → manifest`. To pin that two independent engines normalize
identically, conformance feeds each a sample IPLAN and asserts the produced
manifests are **identical across engines** (cross-engine differential) and each
**validates to `pass`**. The manifest carries `source_iplan_checksum` =
`sha256(file_bytes)`, deterministic for a fixed sample, so cross-engine equality
holds without hard-coding a brittle expected checksum.

**Injected clock (D-0014).** The handover receipt's `created_at` comes from an
**injected clock**, so `build_handover_receipt` is deterministic and
testable, and engines agree.

**Validators are internal-consistency only.** The handover validator checks the
receipt is self-consistent (e.g. `status: completed` ⇒ `gate_status: passed` and
`reconciled: true`); cross-checking a receipt against the *actual* ledger is the
builder's job, not the validator's (keeps validators pure, no I/O).

**Version bump is atomic and last (Task 7).** All version markers stay at
`0.1.0` until the slice is complete, then move to `0.2.0` together
(`framework/VERSION`, registry `spec_version`, both engines'
`FRAMEWORK_SPEC_VERSION`) so spec-parity conformance stays green throughout.

**Engines lag the vectors (TDD).** New vectors (Task 3) reference rules the
engines only implement in Tasks 4–5, so `test_vectors` / `test_rule_catalog`
are red between Task 3 and Task 5 — by design, as in PLAN-001. **Full
conformance is green at Task 6**, not after every intermediate commit.

**Adapter wraps config.** `reader.ingest_iplan(path, config)` is the pure
module function; the adapter method `engine.ingest_iplan(path)` calls it with
the engine's own `Config` (so conformance can call it with no extra args). The
handover builder's `audit_report` argument is optional, and `receipt_id` is
**derived deterministically** from inputs (e.g. from `ledger_ref`) — no ambient
ids (D-0014).

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/intake/IPLAN-INTAKE-TEMPLATE.yaml` | Normalized intake manifest (`iplan-intake`): `intake_control` (source + checksum + `exec_ready_score` + `approved`), `isolation_scope`, `task_graph`. |
| `framework/intake/INTAKE_CONTRACT.md` | Front-door contract: consumed subset, `EXEC_READY_MIN = 90`, SDD→manifest field mapping, no-SDD-dependency note. |
| `framework/handover/IPLAN-HANDOVER-RECEIPT-TEMPLATE.yaml` | Handover receipt (`iplan-handover-receipt`): `handover_control` (refs, `gate_status`, `created_at`) + `result`. |
| `framework/handover/HANDOVER_CONTRACT.md` | Back-door contract + receipt semantics. |
| `framework/conformance/rule-ids.yaml` | + categories `INTAKE-001`, `HANDOVER-001` and their rules. |
| `framework/conformance/RULE-IDS.md` | + new rules table rows. |
| `framework/conformance/vectors/intake/*.yaml(.expect.yaml)` | Valid baseline + one per `INTAKE.*` rule. |
| `framework/conformance/vectors/handover/*.yaml(.expect.yaml)` | Valid baseline + one per `HANDOVER.*` rule. |
| `framework/conformance/intake_samples/<name>/iplan.yaml` | SDD-IPLAN-shaped reader-parity inputs. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + `intake`/`handover` artifacts, protocol docs, `intake_samples_root`. |
| `platforms/<engine>/src/iops_<engine>/intake/reader.py` | `ingest_iplan(path, config) -> manifest` (SDD→manifest mapping). |
| `platforms/<engine>/src/iops_<engine>/config.py` | Thin config: field mapping, ids, paths. |
| `platforms/<engine>/src/iops_<engine>/validation/intake_rules.py` | `validate_intake` (INTAKE.* rules). |
| `platforms/<engine>/src/iops_<engine>/validation/handover_rules.py` | `validate_handover` (HANDOVER.* rules). |
| `platforms/<engine>/src/iops_<engine>/handover/receipt.py` | `build_handover_receipt(ledger, gate_result, audit_report, *, clock)`. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | Dispatch `iplan-intake`/`iplan-handover-receipt`; add `ingest_iplan` + `build_handover` adapter methods. |
| `platforms/<engine>/src/iops_<engine>/cli.py` | `intake <iplan>` and `handover <ledger> <gate>` commands. |
| `platforms/<engine>/tests/` | intake/handover validation + reader + handover-builder tests. |
| `tests/conformance/test_intake_readers.py` | Cross-engine reader parity + manifest validity over `intake_samples/`. |

## Step Sequence

### Task 1: Framework intake contract

- [ ] **Step 1: `IPLAN-INTAKE-TEMPLATE.yaml`** (`document_type: iplan-intake`) —
  `intake_control` (`source_iplan`, `source_iplan_version`,
  `source_iplan_checksum`, `exec_ready_score`, `approved`), `isolation_scope`
  (client/project/allowed_roots), `task_graph` (`task_id`, `title`,
  `depends_on`, `acceptance.criteria`).
- [ ] **Step 2: `INTAKE_CONTRACT.md`** — consumed subset; `EXEC_READY_MIN = 90`;
  default SDD→manifest field mapping (e.g. SDD `document_control.iplan_id` →
  `intake_control.source_iplan`); statement of no SDD-repo dependency.
- [ ] **Step 3: rule-ids** — add category `INTAKE-001` + rules:
  `INTAKE.SCHEMA_UNSUPPORTED`, `INTAKE.SOURCE_MISSING`,
  `INTAKE.APPROVAL_INSUFFICIENT`, `INTAKE.SCOPE_MISSING`, `INTAKE.NO_TASKS`,
  `INTAKE.TASK_FIELDS_MISSING`, `INTAKE.DEP_UNRESOLVED` (all `error`). Update
  `RULE-IDS.md`.
- [ ] **Step 4: registry** — add the `intake` artifact (template +
  `document_type: iplan-intake` + `error_prefix: INTAKE-001`) and
  `INTAKE_CONTRACT.md` to `protocol_docs`.
- [ ] **Step 5: parse check + commit** — `feat: add iplan intake contract`.

### Task 2: Framework handover contract

- [ ] **Step 1: `IPLAN-HANDOVER-RECEIPT-TEMPLATE.yaml`**
  (`document_type: iplan-handover-receipt`) — `handover_control` (`receipt_id`,
  `source_iplan`, `source_iplan_version`, `ledger_ref`, `gate_status`,
  `audit_report_ref`, `created_at`), `result` (`status` ∈ completed|aborted,
  `reconciled`).
- [ ] **Step 2: `HANDOVER_CONTRACT.md`** — receipt semantics + internal
  consistency rules.
- [ ] **Step 3: rule-ids** — category `HANDOVER-001` + rules:
  `HANDOVER.SOURCE_MISSING`, `HANDOVER.GATE_NOT_PASSED`,
  `HANDOVER.NOT_RECONCILED`, `HANDOVER.STATUS_INVALID` (all `error`). Update
  `RULE-IDS.md`.
- [ ] **Step 4: registry** — add the `handover` artifact (template +
  `document_type: iplan-handover-receipt` + `error_prefix: HANDOVER-001`) and
  `HANDOVER_CONTRACT.md` to `protocol_docs`.
- [ ] **Step 5: parse check + commit** — `feat: add iplan handover contract`.

### Task 3: Golden vectors + reader-parity samples

- [ ] **Step 1: intake vectors** — `vectors/intake/valid_intake` (pass) + one
  fail vector per `INTAKE.*` rule, each isolating exactly its rule.
- [ ] **Step 2: handover vectors** — `vectors/handover/valid_receipt` (pass) +
  one per `HANDOVER.*` rule.
- [ ] **Step 3: reader-parity samples** — `intake_samples/minimal/iplan.yaml`
  and `intake_samples/with_deps/iplan.yaml` (SDD-IPLAN-shaped inputs, both
  *approved/valid* so their normalized manifests validate to `pass`); add
  `intake_samples_root` to the registry, and extend `test_registry` to assert it
  exists.
- [ ] **Step 4: coverage self-check + commit** — every new catalog rule has ≥1
  vector. `test: add intake/handover vectors + reader samples`.

### Task 4: Hermes implementation (TDD)

- [ ] **Step 1: failing tests** — intake/handover validator cases (assert rule
  IDs), reader output shape, handover builder (with a fixed clock). Run → fail.
- [ ] **Step 2: `config.py`** — `Config` dataclass with defaults (intake field
  mapping, `exec_ready_min = 90`); load-from-dict.
- [ ] **Step 3: `intake/reader.py`** — `ingest_iplan(path, config) -> manifest`:
  read bytes → checksum; map SDD fields → `intake_control`/`isolation_scope`/
  `task_graph` per `config`.
- [ ] **Step 4: `validation/intake_rules.py` + `validation/handover_rules.py`**
  — emit `INTAKE.*` / `HANDOVER.*` findings; register in `validation/__init__`.
- [ ] **Step 5: `handover/receipt.py`** — `build_handover_receipt(ledger,
  gate_result, audit_report=None, *, clock)`; `created_at = clock()`;
  `receipt_id` derived deterministically from `ledger_ref` (no ambient ids).
- [ ] **Step 6: `engine.py`** — extend `_DISPATCH` with `iplan-intake` /
  `iplan-handover-receipt`; add `ingest_iplan(path)` + `build_handover(...)`;
  update `capabilities()`.
- [ ] **Step 7: `cli.py`** — `intake <iplan>` (ingest → validate → emit
  manifest) and `handover <ledger> <gate>` (run gate → build → validate).
- [ ] **Step 8: green** — `pytest platforms/hermes -q`, `ruff`, `mypy --strict`.
  Commit `feat: add intake/handover to hermes engine`.

### Task 5: Claude implementation (independent)

- [ ] **Step 1–7:** mirror Task 4 as an **independent** copy under `iops_claude`
  (own `intake/`, `config.py`, validators, `handover/`); wire into
  `ClaudeEngine`. No import of `iops_hermes`.
- [ ] **Step 8: green** — `pytest platforms/claude -q`, `ruff`, `mypy --strict`.
  Commit `feat: add intake/handover to claude engine`.

### Task 6: Conformance extension

- [ ] **Step 1: `test_intake_readers.py`** — for each `intake_samples/<name>`,
  run every importable engine's `ingest_iplan`; assert all produced manifests
  are **identical** (cross-engine) and each `validate`s to `pass`. Skip if < 2
  engines import.
- [ ] **Step 2: run full suite** — `python -m unittest discover -s
  tests/conformance -v` (vectors now include intake/handover; catalog coverage
  includes new rules). All green.
- [ ] **Step 3: commit** — `test: add reader-parity conformance`.

### Task 7: Version bump, changelog, handoff

- [ ] **Step 1: bump to `0.2.0`** — `framework/VERSION`, registry
  `metadata.spec_version`, `platforms/hermes/FRAMEWORK_SPEC_VERSION`,
  `platforms/claude/FRAMEWORK_SPEC_VERSION` (atomic).
- [ ] **Step 2:** `CHANGELOG.md` `[Unreleased] → Added`: intake + handover.
- [ ] **Step 3:** update `plans/HANDOFF.md`; set this plan `Status: DONE`.
- [ ] **Step 4: full verification** (below) + commit `chore: release spec v0.2.0
  (intake & handover)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green: intake/handover vectors yield the expected rule-ID sets in
   each engine; engines agree (differential); **reader parity** holds; catalog
   fully covered; spec-version parity at `0.2.0`.
2. Per-engine tests pass (reader maps the sample IPLANs; validators reject the
   bad vectors; handover builder is deterministic under a fixed clock).
3. `ruff` + `mypy --strict` clean.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | We don't have SDD's real IPLAN schema; our mapping may not match. | Tolerant + **configurable** field mapping; mapping documented; samples are the supported shape; drift absorbed in `config.py`, not the core. |
| R2 | Intake/handover vectors trip more than their target rule. | Author each from a clean valid baseline, perturbing one field (the PLAN-001 discipline); coverage + differential tests catch leaks. |
| R3 | Reader parity brittle if it hard-codes the IPLAN checksum. | Compare engine manifests to **each other** (differential) + assert `pass`, not to a hard-coded expected. |
| R4 | Mid-plan version skew breaks spec-parity conformance. | Bump all markers atomically in Task 7; markers stay `0.1.0` until then. |
| R5 | New doc types not added to engine dispatch → validate raises. | Task 4/5 Step 6 extends `_DISPATCH`; reader-parity + vector tests exercise both new types. |
| R6 | Handover validator over-reaches by reading the ledger. | Validator checks **internal consistency only**; ledger cross-checks are the builder's responsibility. |
| R7 | `ingest_iplan` non-determinism (clock/uuid) breaks parity. | No clock in intake; checksum is the only derived field and is byte-deterministic; handover clock is injected (D-0014). |

## Review log

> ≥2 passes before implementation. Each pass: re-read the whole plan, list
> findings, fold fixes into the sections above.

### Pass 1 - 2026-05-23

- Finding: registry artifacts in PLAN-001 carry an `error_prefix` and
  `test_registry` asserts prefixes are unique; the new artifacts omitted it.
  Change: `intake` → `error_prefix: INTAKE-001`, `handover` →
  `error_prefix: HANDOVER-001` (Tasks 1/2 Step 4).
- Finding: adding `intake_samples_root` to the registry without a presence
  check leaves a dangling reference. Change: extend `test_registry` to assert it
  exists (Task 3 Step 3).
- Finding: the run-order makes intermediate commits red (vectors precede engine
  support). Change: stated explicitly in Approach — full conformance is green at
  Task 6, TDD-style (matches PLAN-001).
- Finding: `ingest_iplan` had two signatures (module vs adapter) that could
  confuse the conformance call. Change: clarified — module fn takes `config`,
  adapter method wraps it with the engine's `Config`; conformance calls the
  no-arg adapter form.
- Finding: reader-parity manifests must also *validate to pass*, so the sample
  IPLANs must be approved/valid. Change: noted in Task 3 Step 3.

### Pass 2 - 2026-05-23

- Finding: `receipt_id` / `created_at` could introduce non-determinism and break
  cross-engine agreement. Change: `created_at` from an injected clock and
  `receipt_id` derived from `ledger_ref` (Approach + Task 4 Step 5; R7).
- Finding: handover `result.status: aborted` must not trip the completed-only
  rules (`GATE_NOT_PASSED`, `NOT_RECONCILED`). Confirmed: those rules are guarded
  by `status == "completed"`, so an aborted receipt is valid (`pass`); only
  `STATUS_INVALID` fires for an out-of-set status. No change needed.
- Finding: each fail-vector must isolate exactly one rule (e.g.
  `APPROVAL_INSUFFICIENT` keeps scope/tasks/deps valid). Confirmed as the
  authoring rule in Task 3 (R2); `SCHEMA_UNSUPPORTED`'s vector is otherwise-valid
  so it emits only that rule without needing a short-circuit.
- Verification ↔ rules cross-check: 7 `INTAKE.*` + 4 `HANDOVER.*` rules each map
  to one fail vector plus a valid baseline (13 vector pairs); reader parity adds
  2 samples; catalog coverage + differential + reader-parity tests exercise them
  all. No further findings.
