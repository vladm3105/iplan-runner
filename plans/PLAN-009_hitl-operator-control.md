# Human-in-the-Loop & Operator Control Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** Put a human in the loop (Roadmap Phase 9 → `v0.9.0`): **operator
controls** (pause / resume / abort a run), **blocker resolution**
(approve / reject / override, authorized as `operator`), and **resume** — continue
a paused or crashed run from its persisted, append-only ledger using idempotency.

**Architecture:** Additive (D-0014). New `framework/execution/CONTROL_MODEL.md`,
an injected `control` checkpoint in the run loop, and operator/resume primitives.
Parity: the **control lifecycle** is pinned by an extended scenario (injected
control → resulting `run_state`) + differential; **resolution/resume** flows are
deterministic and tested per-engine (the shared loop is already differential'd).
Operator authz reuses the PLAN-007 `authorize` (`approve`/`override`). Defaults
(control = always running) keep all prior scenarios green — they just gain an
additive `run_state` projection field.

**Tech Stack:** Python ≥3.11; `pytest`; `unittest` conformance; `ruff` +
`mypy --strict`; YAML.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-009 |
| Depends on | `PLAN-001`..`PLAN-008` (DONE); D-0011..D-0015; Roadmap Phase 9 |
| Status     | IN REVIEW - 2026-05-24 |
| Feeds      | observability-driven issue loop (post-v1.0); the SDD approval boundary |

## Objective

A run can block, but nothing lets a human steer it. PLAN-009 adds the controls:

1. **Operator controls.** `pause` / `abort` a run (checkpointed **between
   tasks**), persisted on the ledger as `run_state` (`running` / `paused` /
   `aborted` / `completed`). The run loop consults an injected `control` before
   each task.
2. **Blocker resolution.** `resolve_blocker(ledger, blocker_id, decision, actor)`
   — `approve` / `reject` / `override` — **authorized** (`operator` role, PLAN-007
   `authorize`); records a resolution; `override` resets the task to `pending` so
   it can be retried.
3. **Resume.** `resume(manifest, ledger, executor, ...)` continues a paused or
   crashed run from its **persisted** ledger: completed tasks are skipped
   (idempotency, PLAN-005), pending/overridden tasks run.
4. **CLI** — `pause` / `abort` / `resume` / `resolve` over the ledger store.

## Scope

**In:**

1. `framework/execution/CONTROL_MODEL.md` — `run_state` lifecycle, the between-task
   control checkpoint, blocker-resolution decisions + authz, resume semantics.
   Registry → add the doc.
2. Run loop: an injected `control() -> "running"|"paused"|"aborted"` (default
   `running`), checked before each task; `ledger_control.run_state` recorded.
   Refactor the loop body so `run()` and `resume()` share it.
3. `resolve_blocker(ledger, blocker_id, decision, actor)` — authz-gated; appends a
   `resolutions` entry + a `resolution` event; `override` → task back to `pending`.
4. `resume(manifest, ledger, executor, *, clock, ids, sleep, control)` — drive the
   existing ledger (seed completed from it; idempotency skip) → `RunResult`;
   `control` (default running) lets a resumed run be paused/aborted again.
   The CLI builds `control` to read a **store control flag** (so `pause`/`abort`
   from another process is seen at the next checkpoint); tests inject `control`.
5. Per engine (`hermes`, `claude`, independent): the above + CLI `pause` / `abort`
   / `resume` / `resolve` over the store (a control flag + the persisted ledger);
   tests.
6. Conformance: extend `test_scenarios` projection with `run_state`; thread an
   optional `control` from the scenario; add an `aborted` control scenario;
   regenerate existing expectations (additive). Resume/resolve are per-engine
   integration-tested.
7. Spec bump to `0.9.0`.

**Out:**

1. **Interrupting a task mid-execution** — control is checked **between tasks**;
   a running executor is not killed (best-effort/cooperative; timeouts are the
   in-task bound, PLAN-005). Documented.
2. **Notification transport** (Slack/email/webhook) — blockers are *surfaced*
   (queryable via `status`); push delivery is the observability-driven issue loop
   (post-v1.0).
3. **OIDC operator login** — the operator is an actor with role `operator`
   (authz from PLAN-007); full identity provider wiring is D-0015 / later.
4. Distributed / concurrent control across processes.

## Approach

**Control is injected, default running.** `run(..., control=None)` defaults to a
callable returning `"running"`, so the loop never stops and every prior scenario
is unchanged except for the additive `run_state` (= `completed`). With a scripted
control, the loop checkpoints **before each task**: `aborted` → stop, terminal;
`paused` → stop, **resumable**; remaining tasks stay `pending`. `run_state` is
stamped on `ledger_control`.

**Resume reuses the loop.** The loop body is extracted to `_drive(ledger,
manifest, executor, *, completed, ...)`; `run()` = `_init_ledger` + `_drive(completed
= {})`; `resume()` = load the persisted ledger + `_drive(completed = {already-completed
task_ids})`. The PLAN-005 idempotency skip means committed tasks aren't re-run;
pending (incl. `override`-reset) tasks run. This makes **crash resume** fall out
of persistence + idempotency — no special recovery path.

**Resolution is authorized + recorded.** `resolve_blocker` maps the decision to
an authz action — `override` → `"override"`, `approve`/`reject` → `"approve"`
(both are operator blocker decisions; only these are in the PLAN-007 matrix) —
and calls `authorize(actor, action)`; a denied actor raises. It appends a
`resolutions` entry (`{blocker_id, decision, actor, at}`) + a `resolution`
execution-log event; `override` removes the open blocker and resets the task to
`pending` (so `resume` retries it), `reject` leaves it blocked, `approve` clears
a pending-approval gate.

**`run_state` ≠ `handover_status`.** `run_state` is the *control/loop* lifecycle
(`completed` = the loop ran to the end uninterrupted; `paused`/`aborted` =
control stopped it). It is distinct from `handover_status` (done-ness): e.g.
`failure_blocks` has `run_state: completed` (loop finished) but
`handover_status: aborted` (tasks blocked).

**Parity split.** The **control lifecycle** (injected control → `run_state` +
task outcomes) is pinned by a scenario + differential. **Resolution/resume** are
deterministic over ledger data and tested per-engine (two-phase: run → resolve →
resume); the underlying loop is already differential'd, so parity holds.

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/execution/CONTROL_MODEL.md` | `run_state` lifecycle, control checkpoint, resolution decisions + authz, resume. |
| `framework/conformance/scenarios/aborted/` | Control aborts after T1. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + `CONTROL_MODEL.md`. |
| `platforms/<engine>/src/iops_<engine>/orchestrator/loop.py` | injected `control`; `_drive`; `run_state`; `resume`. |
| `platforms/<engine>/src/iops_<engine>/orchestrator/control.py` | `resolve_blocker` (authz-gated) + resolution recording. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | `resume`, `resolve_blocker`, `pause`/`abort` control helpers. |
| `platforms/<engine>/src/iops_<engine>/ledger/index.py` | control-flag read/write in the store (pause/abort/resume). |
| `platforms/<engine>/src/iops_<engine>/cli/commands.py` | `pause` / `abort` / `resume` / `resolve`. |
| `platforms/<engine>/tests/test_control.py` | abort, pause→resume, override→resume, resolution authz. |
| `tests/conformance/test_scenarios.py` | `run_state` projection + scenario `control`. |

## Step Sequence

### Task 1: Framework control model

- [ ] **Step 1:** `CONTROL_MODEL.md` — `run_state` (`running`/`paused`/`aborted`/
  `completed`), between-task checkpoint, `resolve_blocker` decisions
  (`approve`/`reject`/`override`) + required `operator` authz, resume semantics
  (idempotency-based), and the mid-task-interruption out-of-scope note.
- [ ] **Step 2:** registry — add `CONTROL_MODEL.md` to `protocol_docs`.
- [ ] **Step 3: commit** — `feat: add operator control model`.

### Task 2: Control scenario

- [ ] **Step 1:** `scenarios/aborted/scenario.yaml` — two **independent**
  success tasks; `control: [running, aborted]` (consumed once per task
  checkpoint → T1 runs, abort before T2). `expect.yaml` (T1 completed, T2
  pending, `run_state: aborted`, `handover_status: aborted`) is regenerated in
  Task 3 once the engine exists.
- [ ] **Step 2: commit** — `test: add aborted control scenario input`.

### Task 3: Hermes implementation (TDD)

- [ ] **Step 1: failing tests** — control abort stops before T2 (`run_state
  aborted`, T2 pending); pause then `resume` completes T2; `override` a blocked
  task then `resume` completes it; `resolve_blocker` denies a non-operator actor.
  Fail.
- [ ] **Step 2: loop.py** — extract `_drive`; add injected `control` + checkpoint;
  stamp `run_state`; add `resume(manifest, ledger, ...)` (seed completed from the
  ledger).
- [ ] **Step 3: orchestrator/control.py** — `resolve_blocker` (authz-gated;
  resolution record + event; `override` → task `pending`).
- [ ] **Step 4: engine.py** — `run(..., control=None)`; `resume`,
  `resolve_blocker`; `pause`/`abort` helpers (set the store control flag).
- [ ] **Step 5: ledger/index.py + cli** — control-flag read/write; `pause` /
  `abort` / `resume` / `resolve` commands.
- [ ] **Step 6: (re)generate scenario expectations** — add `run_state` to the
  projection and regenerate all scenario expects (incl. `aborted`).
- [ ] **Step 7: green** — `pytest`, `ruff`, `mypy --strict`. Commit
  `feat: add operator control + resume to hermes`.

### Task 4: Claude implementation (independent)

- [ ] **Step 1–6:** mirror Task 3 as an independent copy. No import of `iops_hermes`.
- [ ] **Step 7: green** + commit `feat: add operator control + resume to claude`.

### Task 5: Conformance

- [ ] **Step 1:** `test_scenarios.py` — add `run_state` to the projection; thread
  an optional `control` (from `scenario.control`, consumed per checkpoint); the
  `aborted` scenario + regenerated expects pass per engine + differential.
- [ ] **Step 2: run full suite** + commit `test: add control-scenario conformance`.

### Task 6: Version bump, changelog, handoff

- [ ] **Step 1:** atomic bump to `0.9.0`.
- [ ] **Step 2:** `CHANGELOG.md` `[0.9.0]`; update `HANDOFF.md`; plan `DONE`.
- [ ] **Step 3: full verification** + commit `chore: release spec v0.9.0
  (HITL & operator control)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green: the `aborted` scenario yields `run_state: aborted` + T2
   pending in each engine + differential; prior scenarios pass with the additive
   `run_state` field; all other checks unchanged at `0.9.0`.
2. Per-engine tests: pause→resume completes the run; override→resume retries a
   blocked task; `resolve_blocker` requires `operator`; resume skips committed
   tasks (idempotency).
3. `ruff` + `mypy --strict` clean.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Control injection changes the loop → breaks prior scenarios. | `control` defaults to `running` (no checkpoint stops); only an additive `run_state` projection field; regenerate expects once. |
| R2 | `_drive` refactor changes `run()` behavior. | `run()` = `_init_ledger` + `_drive(completed={})`, byte-identical; the cross-engine differential + regenerated scenarios guard it. |
| R3 | Resume re-runs completed tasks (double-apply). | PLAN-005 idempotency skip (committed txn) + seeded `completed` set; covered by a resume test. |
| R4 | Mid-task pause expectation. | Out of scope: control is **between tasks**; in-task bound is the saga timeout (PLAN-005); documented. |
| R5 | Unauthorized resolution. | `resolve_blocker` calls `authorize` (`approve`/`override` ⇒ `operator`); denied → raises; tested. |
| R6 | Override masking real failure. | `override` is operator-authorized + recorded (actor + at) in the signed ledger — an auditable, accountable decision, not a silent bypass. |
| R7 | Resume/resolve not cross-engine-differential'd. | The shared run loop is already differential'd; resolution/resume are deterministic over ledger data, per-engine tested; the control lifecycle is scenario-differential'd. |

## Review log

> ≥2 passes before implementation.

### Pass 1 - 2026-05-24

- Finding (bug): the PLAN-007 authz matrix has `approve`/`override` but no
  `reject`, so `resolve_blocker(decision="reject")` would be forbidden even for an
  operator. Change: map `approve`/`reject` → authz action `"approve"`, `override`
  → `"override"` (documented in Approach + Task 3).
- Finding: `resume` needs its own `control` so a resumed run is also
  pausable/abortable; and the CLI's control must read a store flag (cross-process
  operator action). Stated in scope + approach.
- Finding: `run_state: completed` could be read as task-completion. Clarified it
  is the *control/loop* lifecycle, distinct from `handover_status` (with the
  `failure_blocks` example).
- Finding: the `aborted` scenario must make abort-before-T2 meaningful. Change:
  two **independent** success tasks + `control: [running, aborted]` consumed once
  per checkpoint.

### Pass 2 - 2026-05-24

- Finding: `_drive` refactor must keep `run()` byte-identical. Confirmed: `run()`
  = `_init_ledger` + `_drive(completed={})`; the regenerated scenarios + the
  cross-engine differential guard it (R2); control defaults to `running` so no
  checkpoint stops a normal run (R1).
- Finding: crash resume shouldn't be a special path. Confirmed: `resume` = load
  ledger + `_drive(completed=already-done)`; PLAN-005 idempotency skips committed
  tasks — recovery falls out of persistence + idempotency (R3).
- Finding: `override` could mask failure. Confirmed acceptable (R6): it is
  operator-authorized and recorded (actor + `at`) in the HMAC-signed ledger — an
  auditable decision, not a silent bypass.
- Verification ↔ surface cross-check: control lifecycle is scenario-pinned +
  differential; resolution/resume are deterministic over ledger data, per-engine
  tested (incl. authz denial + idempotent resume); the loop is already
  differential'd. No further findings.
