# Saga & Lease Runtime Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** Make execution **robust** (Roadmap Phase 5 → `v0.5.0`). Wrap each
task's execution in a **saga**: idempotency, bounded **retry/backoff** on
retriable failure, **timeout-as-failure**, **compensation** (undo partial
effects — the PLAN-004 R8 debt), and **escalation** to a blocker when
unrecoverable. Add the **lease lifecycle**: acquire (with a concurrency guard),
renew, expire, release.

**Architecture:** Additive (D-0014). Extends `SAGA_EXECUTION_MODEL.md`, adds
`LEASE_MODEL.md`, and updates the executor contract (`retriable`, injected
`sleep`). Two-regime parity (as PLAN-004): **pure** saga/lease *decision* logic
is pinned by scenario + decision vectors and the cross-engine differential
(D-0012); **real** compensation I/O (deleting partial writes) is per-engine
tested. Strict isolation (D-0011) holds. Defaults preserve PLAN-003/004 behavior
(`max_retries = 0`), so existing scenarios are unchanged except for an additive
projection field.

**Tech Stack:** Python ≥3.11; `pytest`; `unittest` conformance; `ruff` +
`mypy --strict`; YAML.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-005 |
| Depends on | `PLAN-001`..`PLAN-004` (DONE); D-0011..D-0014; Roadmap Phase 5 |
| Status     | DONE - 2026-05-24 |
| Feeds      | `PLAN-007` (chain runtime reuses leases + cross-plan saga); `PLAN-009` (resume uses idempotency) |

## Objective

PLAN-003/004 run each task once and, on failure, block it — leaving any partial
effects in place (PLAN-004 R8). PLAN-005 adds the transaction discipline:

1. **Idempotency.** A committed transaction (by `idempotency_key`) is not
   re-executed — a no-op within a run today, the foundation for crash resume
   (Phase 9).
2. **Retry + backoff.** A `retriable` failure is retried up to `max_retries`
   with deterministic backoff (injected `sleep`, so tests don't wait).
3. **Timeout-as-failure.** A reported timeout is a retriable failure (real
   wall-clock interruption is best-effort / Phase 7+).
4. **Compensation.** When a task ultimately fails after applying partial effects,
   the saga **undoes** them (deletes the files it wrote, within the sandbox) and
   records a `compensated` transaction — paying off the PLAN-004 R8 debt.
5. **Escalation.** Unrecoverable failure records a blocker (`decision_owner`),
   leaving the task `blocked`.
6. **Lease lifecycle.** `acquire` refuses to start a task with an active
   overlapping lease (concurrency guard); `renew`/`expire` track the window;
   `release` on completion.

## Scope

**In:**

1. `framework/execution/SAGA_EXECUTION_MODEL.md` — extend with the runtime state
   machine (`pending → committed | compensated`, attempts, retry/backoff,
   idempotency, timeout, escalation). `framework/execution/LEASE_MODEL.md` —
   lease states (`active`/`expired`/`released`) + the `can_acquire` guard.
2. `framework/engines/EXECUTOR-CONTRACT.md` — `ExecutorResult.retriable`; the
   `MockExecutor` per-task **attempt sequence**; injected `sleep`.
3. Per engine (`hermes`, `claude`, independent): `orchestrator/saga.py`
   (attempt loop, backoff, idempotency, compensation, escalation),
   `orchestrator/leases.py` (`lease_state`, `can_acquire`, `renew`, `expire`),
   `effectors/compensate.py` (`undo_writes`); `ExecutorResult.retriable`;
   `MockExecutor` sequences; `Config.max_retries` + `backoff_base`;
   `run(..., sleep=, max_retries=)`; CLI defaults; tests.
4. Conformance: extend the scenario projection with a `saga` summary (`{task_id:
   {status, attempts}}`) and **regenerate** existing scenario expectations
   (additive; behavior unchanged); add saga scenarios `retry_then_succeed`,
   `retry_exhausted_escalate`; add lease decision vectors
   (`framework/conformance/leases/`) + `test_leases.py`; pass `sleep`/`max_retries`
   through `test_scenarios.py`.
5. Spec bump to `0.5.0`.

**Out:**

1. Distributed / cross-process / cross-IPLAN lease coordination — chain runtime,
   PLAN-007.
2. Crash **resume** — Phase 9 (idempotency is the enabler, resume itself deferred).
3. Real wall-clock timeout *interruption* of a running executor — best-effort /
   Phase 7+; here a timeout is a *reported* retriable failure.
4. Live executors — Phase 8.

## Approach

**Defaults preserve current behavior.** `max_retries` defaults to `0`, so a
non-retriable (or any, with 0 retries) failure blocks exactly as in PLAN-004.
The existing four scenarios change only by gaining the additive `saga` projection
field (attempts = 1; status committed/pending) — their event sequences,
statuses, gate, and handover are unchanged, and the cross-engine differential
still holds.

**The attempt loop (in `saga.py`, called by the run loop).**

```
attempt = 0
while True:
    attempt += 1
    result = executor.execute(task, ctx)       # MockExecutor returns the
    if result.outcome == "success": break       #   attempt-th scripted outcome
    if result.retriable and attempt <= max_retries:
        sleep(backoff_base * 2 ** (attempt - 1))  # injected sleep
        continue
    break
txn["attempts"] = attempt
# success -> record evidence/events, commit (PLAN-003 path)
# failure -> compensate(result.touched_paths) if any, then escalate (blocker)
```

A retry happens *inside* the execute step, so **no extra `execution_log` events
per attempt** — the event sequence stays exactly as PLAN-003 pinned it (one
`task_started`, then the outcome events). Retry detail lives in the
`saga_journal` (`attempts`, `status`). The projection's `saga` summary covers
**only tasks with a `saga_journal` entry** (a dependency-unmet-blocked task has
no txn, so it is absent from the summary). `MockExecutor` stays
backward-compatible: a single `{outcome,...}` spec is returned on every call; an
optional `attempts: [...]` list is consumed one-per-call (last repeats).

**Compensation (real undo, per-engine).** On final failure with partial writes,
`undo_writes(touched_paths, workspace)` deletes each written file (sandbox-gated),
the saga appends a `compensation` event and sets the txn `status: compensated`.
In scenarios the mock reports no `touched_paths` on failure (so the control flow
is deterministic with no real files); the real delete is exercised by per-engine
`ScriptedExecutor` tests (write in action 1, denied/failed action 2 → task fails
→ file removed).

**Idempotency.** Before executing, if a committed txn with the task's
`idempotency_key` already exists, skip execution (no-op now; enables Phase-9
resume). Within a fresh run no key pre-exists, so behavior is unchanged.

**Leases (pure decisions + injected clock).** `lease_state(lease, now)` →
`active`/`expired`/`released`; `can_acquire(existing, task_id, now)` is false iff
an `active` lease on `task_id` exists. The run loop calls `can_acquire` before
starting (always true in a sequential run; the guard matters for future
concurrency). `renew(lease, new_expiry)` / `expire` operate on the record. These
pure decisions are vector'd + differential'd.

**Determinism.** `sleep` and `clock` are injected (D-0014); backoff is a pure
function of `attempt`; conformance passes a **no-op sleep** so retry scenarios
run instantly and identically across engines.

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/execution/SAGA_EXECUTION_MODEL.md` | + runtime state machine (retry/backoff/idempotency/timeout/compensation/escalation). |
| `framework/execution/LEASE_MODEL.md` | Lease states + `can_acquire` guard. |
| `framework/engines/EXECUTOR-CONTRACT.md` | + `retriable`, attempt sequences, injected `sleep`. |
| `framework/conformance/scenarios/{retry_then_succeed,retry_exhausted_escalate}/` | New saga scenarios. |
| `framework/conformance/leases/<name>/{input.yaml,expect.yaml}` | `can_acquire` decision vectors. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + `LEASE_MODEL.md`, + `leases_root`. |
| `platforms/<engine>/src/iops_<engine>/orchestrator/saga.py` | Attempt loop, backoff, idempotency, compensation, escalation. |
| `platforms/<engine>/src/iops_<engine>/orchestrator/leases.py` | `lease_state`, `can_acquire`, `renew`, `expire`. |
| `platforms/<engine>/src/iops_<engine>/orchestrator/loop.py` | Use saga + lease guard; thread `sleep`/`max_retries`. |
| `platforms/<engine>/src/iops_<engine>/effectors/compensate.py` | `undo_writes(touched_paths, workspace)`. |
| `platforms/<engine>/src/iops_<engine>/executor/{base,mock}.py` | `retriable`; per-task attempt sequence. |
| `platforms/<engine>/src/iops_<engine>/config.py` | `max_retries`, `backoff_base`. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | `run(..., sleep=, max_retries=)`. |
| `platforms/<engine>/tests/test_saga.py` | Retry, idempotency, compensation (real undo), leases. |
| `tests/conformance/test_leases.py` | Cross-engine `can_acquire` parity. |
| `tests/conformance/test_scenarios.py` | Thread `sleep`/`max_retries`; saga projection. |

## Step Sequence

### Task 1: Framework saga/lease contracts

- [ ] **Step 1:** extend `SAGA_EXECUTION_MODEL.md` (runtime state machine,
  retry/backoff, idempotency, timeout-as-failure, compensation, escalation).
- [ ] **Step 2:** `LEASE_MODEL.md` (states + `can_acquire`); update
  `EXECUTOR-CONTRACT.md` (`retriable`, attempt sequences, injected `sleep`).
- [ ] **Step 3:** registry — add `LEASE_MODEL.md` to `protocol_docs`, add
  `leases_root: framework/conformance/leases`.
- [ ] **Step 4: commit** — `feat: add saga runtime + lease model contracts`.

### Task 2: Lease vectors + saga scenario inputs

- [ ] **Step 1:** lease decision vectors (hand-authored; no engine needed) —
  `free` (no leases → allow), `conflict` (active lease on task → deny),
  `expired` (lease past expiry → allow), `released` (released lease → allow).
- [ ] **Step 2:** saga scenario **inputs** (`scenario.yaml` only) —
  `retry_then_succeed` (`max_retries: 2`, T1 fails-retriable then succeeds) and
  `retry_exhausted_escalate` (`max_retries: 1`, T1 fails-retriable twice). The
  `expect.yaml` projections (and the four regenerated existing ones) are produced
  in Task 3, once the engine exists — as in PLAN-003, projections require a
  working engine.
- [ ] **Step 3: commit** — `test: add lease vectors + saga scenario inputs`.

### Task 3: Hermes implementation (TDD)

- [ ] **Step 1: failing tests** — `lease_state`/`can_acquire`/`renew`/`expire`;
  saga retry (fail→succeed) with no-op sleep; retry-exhausted → blocked;
  idempotency skip; real compensation (ScriptedExecutor partial write then failed
  action → file removed, txn `compensated`). Fail.
- [ ] **Step 2: `executor/base.py` + `mock.py`** — `ExecutorResult.retriable`;
  `MockExecutor` consumes a per-task attempt sequence (stateful counter).
- [ ] **Step 3: `orchestrator/leases.py`** — pure lease decisions.
- [ ] **Step 4: `effectors/compensate.py`** — `undo_writes` (sandbox-gated delete).
- [ ] **Step 5: `orchestrator/saga.py`** — attempt loop + backoff + idempotency +
  compensation + escalation; emits `compensation` event + `compensated` txn.
- [ ] **Step 6: `orchestrator/loop.py`** — call the saga per task; `can_acquire`
  guard before lease; thread `sleep`/`max_retries`. Preserve the PLAN-003 event
  sequence on the success/simple-failure paths.
- [ ] **Step 7: `config.py` + `engine.py`** — `max_retries`/`backoff_base`;
  `run(..., sleep=None, max_retries=None)` falling back to config/defaults
  (`time.sleep`, `config.max_retries`) so existing callers are unaffected.
- [ ] **Step 8: (re)generate scenario expectations** — with hermes saga working,
  generate `expect.yaml` for the two new scenarios and regenerate the four
  existing ones with the additive `saga` summary (as in PLAN-003).
- [ ] **Step 9: green** — `pytest platforms/hermes -q`, `ruff`, `mypy --strict`.
  Commit `feat: add saga + lease runtime to hermes`.

### Task 4: Claude implementation (independent)

- [ ] **Step 1–7:** mirror Task 3 as an independent copy under `iops_claude`. No
  import of `iops_hermes`.
- [ ] **Step 8: green** + commit `feat: add saga + lease runtime to claude`.

### Task 5: Conformance

- [ ] **Step 1: `test_leases.py`** — cross-engine `can_acquire` parity over the
  lease vectors.
- [ ] **Step 2: `test_scenarios.py`** — read optional `max_retries` from the
  scenario, pass a **no-op sleep**, and add the `saga` summary to the projection;
  extend `test_registry` path check to `leases_root`.
- [ ] **Step 3: run full suite** + commit `test: add saga/lease conformance`.

### Task 6: Version bump, changelog, handoff

- [ ] **Step 1:** atomic bump to `0.5.0`.
- [ ] **Step 2:** `CHANGELOG.md` `[0.5.0]`; update `HANDOFF.md`; plan `DONE`.
- [ ] **Step 3: full verification** + commit `chore: release spec v0.5.0
  (saga & lease runtime)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green: saga scenarios (retry-then-succeed, retry-exhausted) match
   `expect` per engine + differential; lease decisions match + agree; all prior
   checks pass at `0.5.0`.
2. Per-engine tests: retry/backoff with no-op sleep; idempotency skip;
   **real compensation** removes partial writes and marks the txn `compensated`;
   lease guard/renew/expire.
3. `ruff` + `mypy --strict` clean.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Saga changes break PLAN-003/004 scenarios. | `max_retries=0` default; retries inside execute (no new events); only an additive `saga` projection field; regenerate expectations once. |
| R2 | Retry/backoff non-determinism. | `sleep` injected (no-op in tests); backoff is a pure function of attempt; `clock` injected. |
| R3 | Compensation real I/O can't be scenario-vector'd. | Saga *control flow* via mock scenarios (no real files); real `undo_writes` per-engine tested (R-pattern from PLAN-004). |
| R4 | Compensation deletes outside the sandbox. | `undo_writes` is sandbox-gated (reuses `classify_path`); only deletes paths it recorded writing. |
| R5 | `MockExecutor` statefulness leaks across runs. | Counter is per-`MockExecutor` instance; a fresh executor per run (conformance builds one per scenario). |
| R6 | Idempotency adds hidden complexity with no payoff yet. | Minimal: skip if a committed txn with the key exists; documented as the Phase-9 resume enabler; no behavior change in a fresh run. |
| R7 | `run()` signature change ripples. | New params are keyword with defaults; CLI/PLAN-003 callers unaffected; conformance opts in. |
| R8 | Compensation leaves the ledger inconsistent (deleted files still in `file_edited` events). | Append-only: the `file_edited` events stay (history is truthful); a `compensation` event + `compensated` txn record the undo. The gate/handover treat the task as blocked. |

## Review log

> ≥2 passes before implementation.

### Pass 1 - 2026-05-24

- Finding (ordering): scenario `expect.yaml` projections require a working engine
  (they include the new `saga` summary with `attempts`), so they can't be
  authored in Task 2 before the engine exists. Change: Task 2 authors lease
  vectors + saga scenario **inputs**; Task 3 Step 8 (re)generates all
  expectations once hermes saga works (mirrors PLAN-003). Conformance is red
  between Task 2 and Task 3, by design.
- Finding: conformance must override `max_retries` per scenario and inject a
  no-op sleep, but the CLI must keep defaults. Change: `run(..., sleep=None,
  max_retries=None)` falls back to config/`time.sleep`; conformance opts in.
- Finding: a dependency-unmet-blocked task has no `saga_journal` txn, so the
  `saga` summary must cover only journal entries (else missing-key drift). Stated
  explicitly.
- Finding: `MockExecutor` must stay backward-compatible for the existing four
  scenarios. Change: single-spec behavior preserved; `attempts: [...]` is opt-in.

### Pass 2 - 2026-05-24

- Finding: compensation emits a `compensation` event only when there are partial
  writes; the mock failure path reports no `touched_paths`, so saga *control
  flow* scenarios stay event-stable and deterministic, while **real** compensation
  (event + file delete) is per-engine tested (R3). Confirmed no event-sequence
  change for the existing scenarios (R1).
- Finding: append-only integrity vs compensation — deleting a file doesn't erase
  its `file_edited` event. Confirmed correct (R8): history stays truthful; a
  `compensation` event + `compensated` txn record the undo; the task is `blocked`.
- Finding: `undo_writes` must not delete outside the sandbox. Confirmed it reuses
  `classify_path` and only deletes recorded write paths (R4).
- Verification ↔ surface cross-check: pure decisions (`can_acquire`, saga
  attempt flow) are vector'd + differential; real compensation I/O is per-engine
  tested; defaults (`max_retries=0`) keep prior phases green. No further findings.
