# Execution Core & Run Loop Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** The keystone (Roadmap Phase 3 → `v0.3.0`): turn the validated
`iplan-intake` manifest (PLAN-002) into a **running engine**. An orchestrator
drives the task graph through the state machine, dispatching each task to a
pluggable **`Executor`** (with a deterministic **`MockExecutor`**), recording
every step into a durably-persisted, hash-chained ledger, with the gate wired as
a completion **veto** — exposed as `iops-<engine> run`.

**Architecture:** Additive (D-0014). New engine-agnostic contracts
(`framework/execution/RUN_MODEL.md`, `framework/engines/EXECUTOR-CONTRACT.md`)
and a new conformance kind (`framework/conformance/scenarios/`). Each engine
gains `orchestrator/`, `executor/`, `ledger/` persistence, and a `cli/` package.
Determinism is injected (clock + id source, D-0014) so independent engines
produce **identical** ledgers — pinned by **scenario vectors** (D-0012) plus a
cross-engine differential. Strict isolation (D-0011) holds.

**Tech Stack:** Python ≥3.11; `pytest`; `unittest` conformance; `ruff` +
`mypy --strict`; YAML scenarios.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-003 |
| Depends on | `PLAN-001`, `PLAN-002` (DONE); D-0011..D-0014; Roadmap Phase 3 |
| Status     | DONE - 2026-05-24 |
| Feeds      | `PLAN-004` (effectors/evidence make the executor's effects real); `PLAN-005` (saga/lease runtime); `PLAN-006` (handover ↔ landing) |

## Objective

PLAN-002 produces a validated `iplan-intake` manifest but nothing executes it.
PLAN-003 builds the control flow:

1. **Orchestrator.** From a manifest, build an initial ledger (tasks `pending`),
   compute a dependency order, and drive each task through
   `pending → in_progress → completed | blocked`, appending hash-chained,
   isolation-scoped events at every transition, then reconcile.
2. **Pluggable `Executor` (D-0013).** A typed interface the orchestrator calls
   per task; a deterministic **`MockExecutor`** scripted with per-task outcomes.
   Live executors are Phase 8 — the run loop is executor-agnostic.
3. **Durable state store (G5).** Atomic, lock-guarded, crash-safe ledger
   persistence + a status/query surface (list runs, show a run's status).
4. **Gate-as-veto.** The verification gate runs at the completion boundary and
   vetoes a `completed` handover when the ledger doesn't pass.
5. **`iops-<engine> run <iplan>`.** End-to-end: ingest → orchestrate (mock
   executor) → persist → gate → handover receipt.
6. **Scenario-vector conformance.** Op-scripted runs whose resulting ledger
   (projection + full differential) is pinned across engines.

This is the *control flow only*. The executor's effects are **simulated** by the
mock; making edits/commands real (effectors) and evidence real is PLAN-004;
saga retries/timeouts/compensation and full lease semantics are PLAN-005.

## Scope

**In:**

1. `framework/execution/RUN_MODEL.md` — run-level lifecycle + the **exact
   event-emission sequence** the orchestrator must follow (so independent
   engines emit byte-identical ledgers).
2. `framework/engines/EXECUTOR-CONTRACT.md` — the `Executor` interface,
   `ExecutorResult`, `ExecutionContext`, the injected `clock` / `id source`
   signatures, and the scenario `mock_outcomes` schema.
3. `framework/conformance/scenarios/<name>/{scenario.yaml,expect.yaml}` +
   `scenarios_root` in the registry.
4. Per engine (`hermes`, `claude`, independent): `orchestrator/`
   (`loop.py`, `state.py`, `topo.py`), `executor/` (`base.py`, `mock.py`),
   `ledger/persistence.py` + `ledger/index.py`; refactor `cli.py` → `cli/`
   package with `run` + `status` + existing commands; engine adapter methods
   `run(manifest, executor, *, clock, ids)`, `mock_executor(outcomes)`,
   `default_executor()`; tests.
5. Conformance: `tests/conformance/test_scenarios.py` (per-engine projection ==
   expect + cross-engine full-ledger differential); registry path check for
   `scenarios_root`.
6. Spec bump to `0.3.0`.

**Out:**

1. Real effectors / sandboxed apply / running real acceptance checks — PLAN-004
   (the mock returns simulated `touched_paths` + evidence).
2. Saga retry/timeout/compensation; full lease renew/expire/concurrency —
   PLAN-005 (basic acquire/release + journal entries only here).
3. Live model/host executors — Phase 8.
4. Real VCS landing — Phase 6; crash **resume** — Phase 9 (we persist, we don't
   resume yet).
5. New validation rule IDs — the orchestrator emits standard ledgers validated
   by existing `IPLAN-007` rules; scenarios pin behavior, not new rules.

## Approach

**The manifest → ledger transform.** The orchestrator initializes
`ledger_control` (bound to the manifest's source), copies `isolation_scope`, and
creates a `task_ledger` entry (`pending`) per `task_graph` node. Dependency order
is a topological sort of `depends_on`.

**`run(...)` returns a `RunResult`** = `{ledger, gate_result}`, and validates the
manifest first (reusing PLAN-002's `validate_intake`); a failing manifest aborts
the run before any ledger work (R8).

**Per-task loop (pinned by RUN_MODEL).** For each task in order:
acquire lease → `pending→in_progress` (+`task_started` event) → call
`executor.execute(task, ctx)` → on `success`: append `file_edited` event(s) for
`touched_paths`, add an `execution_evidence` entry *if the executor supplied
one*, set `acceptance.result=pass`, `in_progress→completed`; on `failure`: add a
`blocker` (default `decision_owner`), `in_progress→blocked` → release lease.
After all tasks: compute `reconciliation` (allowed iff no pending/in_progress and
no open blockers), then run the **default gate**.

**Completion vs the gate (two distinct conditions).** The verification gate
validates ledger *well-formedness* (the `GATE-LEDGER` rules), **not** whether
every task finished — that is what `reconciliation.allowed` signals. A run
reaches the terminal `completed` handover status **only when reconciled *and*
gate-passed**; the gate is therefore an independent **veto** (a malformed but
reconciled ledger is still forced to `aborted`). The run uses a built-in
`default_gate()` (each engine's own copy of the standard `GATE-LEDGER-001..005`
rules); it does not read a gate file at runtime.

**Determinism is injected (D-0014).** `run(...)` takes a `clock() -> str` and an
`ids(prefix) -> str`. Every timestamp and every generated id (lease, evidence,
txn) comes from these. The hash chain (PLAN-001 algorithm) is therefore fully
determined by the scenario, so two independent engines produce **identical**
ledgers. The CLI is the composition root that supplies a real clock + counter;
conformance supplies a fixed clock seed + deterministic counter.

**Executor seam (D-0013).** `Executor.execute(task, ctx) -> ExecutorResult`
(`outcome`, `touched_paths`, `evidence`). `MockExecutor(outcomes)` returns the
scripted result for a task id (default `success`, no paths, generic evidence,
when unscripted). Scenarios script `mock_outcomes` per the EXECUTOR-CONTRACT.

**Persistence (G5).** `ledger/persistence.py`: `save(ledger, store_dir)` writes
`<store>/<ledger_id>.yaml` atomically (temp file + `os.replace`) under an
advisory lock; `load(...)` verifies the hash chain on read. `ledger/index.py`:
`list_runs(store_dir)` and `status(ledger_id, store_dir)` (derived counts +
reconciliation + last gate). Single-process safety now; cross-process/distributed
leases are PLAN-005.

**Parity via scenarios (D-0012).** A scenario = `scenario.yaml` (an
`iplan-intake` manifest + `clock_start` + `mock_outcomes`) and `expect.yaml` (a
**projection** of the run: per-task `{status, has_evidence}`, `reconciliation`,
ordered `log_events` as `{event_type, subject_id, touched_paths}` (no
hashes/timestamps), the `gate` verdict, and the `handover_status`
(`completed`/`aborted`)). Conformance computes the projection from each engine's
`RunResult` — `gate` from `gate_result`, `handover_status` from
`engine.build_handover(ledger, gate_result).result.status` (tying in PLAN-002) —
and asserts it equals `expect`; **and** asserts engines produce identical full
ledgers (cross-engine differential). The projector lives in the conformance
harness — the ledger is the contract artifact, so engines need no shared
projector.

**`cli/` package (D-0014).** `cli.py` becomes `cli/` (`__init__.py` exposing
`main`, plus per-group modules); the console-script entry `iops_<engine>.cli:main`
is preserved.

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/execution/RUN_MODEL.md` | Run lifecycle + exact orchestrator event-emission order. |
| `framework/engines/EXECUTOR-CONTRACT.md` | `Executor` / `ExecutorResult` / `ExecutionContext`, injected clock+ids, `mock_outcomes` schema. |
| `framework/conformance/scenarios/<name>/scenario.yaml` | Manifest + `clock_start` + `mock_outcomes`. |
| `framework/conformance/scenarios/<name>/expect.yaml` | Expected ledger projection. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + `scenarios_root`, + new protocol docs. |
| `platforms/<engine>/src/iops_<engine>/orchestrator/state.py` | Task-state transitions (the state machine). |
| `platforms/<engine>/src/iops_<engine>/orchestrator/topo.py` | Dependency topological order. |
| `platforms/<engine>/src/iops_<engine>/orchestrator/loop.py` | `run(manifest, executor, *, clock, ids) -> RunResult{ledger, gate_result}`. |
| `platforms/<engine>/src/iops_<engine>/executor/base.py` | `Executor` Protocol, `ExecutorResult`, `ExecutionContext`. |
| `platforms/<engine>/src/iops_<engine>/executor/mock.py` | `MockExecutor(outcomes)`. |
| `platforms/<engine>/src/iops_<engine>/ledger/persistence.py` | Atomic, lock-guarded save/load (chain-verified). |
| `platforms/<engine>/src/iops_<engine>/ledger/index.py` | `list_runs`, `status`. |
| `platforms/<engine>/src/iops_<engine>/cli/__init__.py` | `main(argv)->int` dispatch (replaces `cli.py`). |
| `platforms/<engine>/src/iops_<engine>/cli/commands.py` | Command handlers incl. `run`, `status`. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | + `run`, `mock_executor`, `default_executor`; capabilities `execute`/`persist`. |
| `platforms/<engine>/tests/test_orchestrator.py` | Run-loop unit + integration tests. |
| `tests/conformance/test_scenarios.py` | Per-engine projection == expect + cross-engine differential. |

## Step Sequence

### Task 1: Framework run-model + executor contract

- [ ] **Step 1: `RUN_MODEL.md`** — run-level lifecycle (`created → running →
  reconciled`); terminal **handover** status `completed` iff
  `reconciliation.allowed` **and** gate passed, else `aborted` (the gate is an
  independent veto, not the completion signal); the **exact event sequence** per
  task (`task_started`, then `file_edited` per touched path in listed order, then
  completion/block), id/timestamp ordering, the stable topo tie-break, and the
  reconciliation rule. This is what makes engines' ledgers byte-identical.
- [ ] **Step 2: `EXECUTOR-CONTRACT.md`** — `Executor.execute(task, ctx) ->
  ExecutorResult{outcome, touched_paths, evidence}`; `ExecutionContext{task,
  isolation_scope, clock, ids}`; `clock()->iso`, `ids(prefix)->str`;
  `mock_outcomes` schema (`{task_id: {outcome, touched_paths?, evidence?}}`).
- [ ] **Step 3: registry** — add both docs to `protocol_docs`; add
  `scenarios_root: framework/conformance/scenarios`.
- [ ] **Step 4: commit** — `feat: add run-model + executor contract`.

### Task 2: Scenario vectors

- [ ] **Step 1:** `scenarios/all_success/` — 2 independent tasks succeed → both
  `completed`, reconciled, gate `passed`, `handover_status: completed`.
- [ ] **Step 2:** `scenarios/dep_order/` — T2 depends on T1; assert T1's events
  precede T2's in `log_events`; both completed.
- [ ] **Step 3:** `scenarios/failure_blocks/` — T1 fails → `blocked` + open
  blocker; `reconciliation.allowed: false`; gate **`passed`** (ledger is
  well-formed); `handover_status: aborted` (not reconciled).
- [ ] **Step 4:** `scenarios/gate_veto/` — task succeeds but the mock supplies
  **no evidence**; orchestrator optimistically completes it, so reconciliation is
  allowed, **but** the gate **`failed`** (`LEDGER.EVIDENCE_REQUIRED`) →
  `handover_status: aborted`. Demonstrates the gate as an independent veto.
- [ ] **Step 5:** hand-write each `expect.yaml` projection; commit
  `test: add execution scenario vectors`.

### Task 3: Hermes implementation (TDD)

- [ ] **Step 1: failing tests** — `topo` order; `state` transitions; `loop.run`
  over a scripted mock → expected ledger; persistence round-trip
  (chain-verified); `index.status`. Run → fail.
- [ ] **Step 2: `executor/base.py` + `mock.py`** — interface + `MockExecutor`.
- [ ] **Step 3: `orchestrator/topo.py`** — deterministic topological sort
  (stable tie-break by `task_id`).
- [ ] **Step 4: `orchestrator/state.py`** — transition helpers appending
  history + hash-chained events (reuse `ledger/store.append_event`).
- [ ] **Step 5: `orchestrator/loop.py`** — `run(manifest, executor, *, clock,
  ids) -> RunResult`: validate the manifest (abort on fail); build ledger;
  iterate topo order per RUN_MODEL; reconcile; run `default_gate()`; return
  `RunResult{ledger, gate_result}`. Add a `default_gate()` (engine's own copy of
  the `GATE-LEDGER` rules).
- [ ] **Step 6: `ledger/persistence.py` + `ledger/index.py`** — atomic
  save/load + lock; chain verify on load; `list_runs`, `status`.
- [ ] **Step 7: `engine.py`** — `run`, `mock_executor`, `default_executor`;
  extend `capabilities`.
- [ ] **Step 8: `cli/` package** — refactor `cli.py` → `cli/` (preserve
  `iops_hermes.cli:main`); add `run <iplan> [--store DIR]` (ingest → run with
  `default_executor()` → persist → handover) and `status [ledger_id] [--store
  DIR]`. Default store `.iops/ledgers`. Smoke-test the console entry (R4).
- [ ] **Step 9: green** — `pytest platforms/hermes -q`, `ruff`, `mypy --strict`.
  Commit `feat: add execution core + run loop to hermes`.

### Task 4: Claude implementation (independent)

- [ ] **Step 1–8:** mirror Task 3 as an independent copy under `iops_claude`
  (own `orchestrator/`, `executor/`, persistence, `cli/`); wire into
  `ClaudeEngine`. No import of `iops_hermes`.
- [ ] **Step 9: green** — `pytest platforms/claude -q`, `ruff`, `mypy --strict`.
  Commit `feat: add execution core + run loop to claude`.

### Task 5: Scenario conformance

- [ ] **Step 1: `test_scenarios.py`** — for each scenario × importable engine:
  build the engine's `mock_executor(scenario.mock_outcomes)` + a fixed clock
  (`clock_start`, +1s/event) + deterministic `ids`; call `engine.run(...)`;
  compute the projection (statuses + `log_events` from `result.ledger`, `gate`
  from `result.gate_result`, `handover_status` from
  `engine.build_handover(result.ledger, result.gate_result)`) and assert it
  equals `expect`. Then assert all engines produced **identical** full ledgers
  (skip the differential when < 2 engines import).
- [ ] **Step 2:** extend `test_registry` path check to `scenarios_root`.
- [ ] **Step 3: run full suite** + commit `test: add scenario conformance`.

### Task 6: Version bump, changelog, handoff

- [ ] **Step 1:** atomic bump to `0.3.0` (framework/VERSION, registry, both
  engines' `FRAMEWORK_SPEC_VERSION` + package versions).
- [ ] **Step 2:** `CHANGELOG.md` `[0.3.0]`; update `HANDOFF.md`; set plan `DONE`.
- [ ] **Step 3: full verification** (below) + commit `chore: release spec v0.3.0
  (execution core & run loop)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green: scenarios — each engine's resulting-ledger projection
   equals `expect`, and engines produce **identical** full ledgers; all prior
   checks (vectors, reader parity, isolation, parity) still pass at `0.3.0`.
2. Per-engine tests: topo order, state transitions, run loop, persistence
   round-trip (chain-verified), gate veto on the failure scenario.
3. `iops-<engine> run <iplan>` produces + persists a ledger and a handover
   receipt; `status` reports it.
4. `ruff` + `mypy --strict` clean.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Independent engines emit different event sequences → full-ledger differential fails. | `RUN_MODEL.md` pins the exact event-emission order; differential test enforces it; fix the engine, never the test. |
| R2 | Non-determinism (clock/ids/hashes) breaks parity. | Inject `clock` + `ids` into `run`; CLI supplies real ones, conformance supplies fixed; hashes derive from these (D-0014). |
| R3 | Hand-authored `expect` projections drift / are wrong. | Projection is small + semantic (status/events/recon/gate); differential is the secondary guard; valid scenarios kept minimal. |
| R4 | `cli.py → cli/` refactor breaks the console entry. | Keep `main` importable as `iops_<engine>.cli:main`; smoke-test the entry. |
| R5 | Scope creep into real effects/saga/leases. | Mock simulates effects; basic lease acquire/release + journal only; retries/timeouts/compensation are PLAN-005 (explicit Out). |
| R6 | Persistence races / partial writes. | Atomic temp-file + `os.replace`; advisory lock; chain verify on load. Distributed locking deferred (PLAN-005). |
| R7 | Topological sort nondeterministic across engines. | Stable tie-break by `task_id`; documented in RUN_MODEL. |
| R8 | A scenario manifest fails intake validation, derailing the run. | Scenario manifests are valid `iplan-intake` (reuse PLAN-002 validator as a precondition in `run`). |

## Review log

> ≥2 passes before implementation.

### Pass 1 - 2026-05-24

- Finding (substantive): the draft used "gate failed" as the signal for an
  incomplete run, but the `GATE-LEDGER` gate validates ledger *well-formedness*,
  not completion — a blocked run produces a *well-formed* ledger that passes the
  gate. Change: completion is `reconciliation.allowed` **and** gate-passed;
  reframed the gate as an independent **veto**; the terminal `handover_status`
  (completed/aborted) is the run outcome. Updated Approach + RUN_MODEL + the
  `failure_blocks` scenario (gate `passed`, handover `aborted`).
- Finding: with the orchestrator always adding evidence, the gate veto could
  never actually fire, so it'd be untested. Change: added a `gate_veto` scenario
  (executor success but no evidence → optimistic complete → gate fails
  `EVIDENCE_REQUIRED` → handover aborted), exercising the veto.
- Finding: `run` return type was inconsistent (`ledger` vs `(ledger,
  gate_result)`). Change: `run -> RunResult{ledger, gate_result}` everywhere;
  projection's `gate`/`handover_status` derive from it (ties in PLAN-002's
  `build_handover`).
- Finding: the gate document source at runtime was unspecified. Change: each
  engine ships a built-in `default_gate()` (its own copy of `GATE-LEDGER` rules);
  no file read at runtime.
- Finding: `run` should refuse an invalid manifest. Change: `run` validates via
  `validate_intake` first and aborts on failure (R8).

### Pass 2 - 2026-05-24

- Finding: cross-engine full-ledger differential only holds if event emission is
  byte-identical. Confirmed mitigation: RUN_MODEL pins the exact event order +
  stable topo tie-break + injected clock/ids; the differential test enforces it
  (R1, R2, R7). No change beyond making the tie-break explicit in Task 1 Step 1.
- Finding: the conformance projector needs the gate verdict + handover status,
  which aren't in the ledger. Resolved: it reads them from `RunResult.gate_result`
  and `engine.build_handover(...)`, not the ledger — documented in Task 5 Step 1.
- Finding: `dep_order` parity must assert *ordering*, not just final statuses.
  Confirmed: `log_events` is an ordered list in the projection, so T1-before-T2
  is checked.
- Scope check: real effects/saga/leases/VCS/resume are all explicitly Out;
  the mock simulates effects and only basic lease acquire/release + journal
  entries are produced. No further findings.
