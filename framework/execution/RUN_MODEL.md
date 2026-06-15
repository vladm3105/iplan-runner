# Run Model

How an engine executes an approved `iplan-intake` manifest (PLAN-002) into a
completed, gated, persisted ledger. This document pins the **exact** orchestration
behavior so independent engines (D-0011) produce **byte-identical** ledgers for
the same inputs (enforced by scenario differential, D-0012).

## Run lifecycle

```
created ──▶ running ──▶ reconciled ──▶ (handover)
```

A run is driven by `run(manifest, executor, *, clock, ids) -> RunResult` where
`RunResult = {ledger, gate_result}`.

1. **created** — validate the manifest (`validate_intake`); abort the run if it
   does not pass. Build the initial ledger: `ledger_control` bound to the
   manifest source (`ledger_id = "LEDGER-" + source_iplan`), copy
   `isolation_scope`, and one `task_ledger` entry per `task_graph` node, status
   `pending`.
2. **running** — process tasks in dependency order (below).
3. **reconciled** — set `reconciliation.allowed = (no pending/in_progress tasks
   and no open blockers)` with the counts.
4. **gate** — run `default_gate()` over the ledger.

## Completion vs the gate

The gate (`GATE-LEDGER-001..005`) validates ledger **well-formedness**, not
completion. The terminal handover status is:

```
completed   iff  reconciliation.allowed AND gate passed
aborted     otherwise
```

The gate is therefore an independent **veto**: a reconciled but malformed ledger
is still `aborted`.

## Dependency order

Tasks run in a topological order of `task_graph[].depends_on`, with a **stable
tie-break by `task_id`** (lexicographic) among ready tasks, so the order is
deterministic across engines.

## Unmet dependencies

Before running a task, all of its `depends_on` must be `completed`. If any
dependency did not complete (blocked or itself dependency-blocked), the task is
**blocked without execution**: append a blocker (`decision_owner: "operator"`,
reason `"dependency not satisfied"`), transition `pending → blocked`, and append
a single `task_blocked` event — no lease, transaction, or `task_started`.

## Per-task event sequence (exact)

For a task whose dependencies are satisfied, in order, the orchestrator performs
these steps. `clock()` is
called once per timestamp in this order; `ids(prefix)` yields `prefix1`,
`prefix2`, … per prefix.

1. Acquire lease: `lease_id = ids("L")`, `acquired_at = clock()` → append to
   `agent_leases` (`released_at` set in step 6).
2. Open transaction: `txn_id = ids("TX")` → append to `saga_journal`
   (`status: pending`, `idempotency_key = "<task_id>-execute"`).
3. Transition `pending → in_progress`: append `execution_log` event
   `task_started` (`subject_id = task_id`, `at = clock()`, `touched_paths: []`)
   and an `execution_history` entry reusing that `at`.
4. Call `executor.execute(task, ctx)`.
5. **On `success`:**
   - For each path in `result.touched_paths` (listed order): append
     `execution_log` event `file_edited` (`subject_id = task_id`,
     `at = clock()`, `touched_paths: [path]`).
   - If `result.evidence` is supplied: `evidence_id = ids("EV")` → append to
     `execution_evidence`; set the task's `acceptance.result = "pass"`.
   - Transition `in_progress → completed`: append `task_completed` event
     (`at = clock()`) + history; set `saga_journal` txn `status: committed`.

   **On `failure`:**
   - `blocker_id = ids("B")` → append to `blockers` (`decision_owner: "operator"`).
   - Transition `in_progress → blocked` (`blocked_reason` from the result):
     append `task_blocked` event (`at = clock()`) + history; leave the txn
     `status: pending`.
6. Release lease: `released_at = clock()` on the lease.

Evidence and history entries reuse the timestamps above (no extra `clock()`
calls), keeping the call sequence fixed.

## Determinism

All time and ids are **injected** (D-0014): the CLI supplies a real clock + a
counter; conformance supplies a fixed clock (`clock_start`, +1s per call) and a
per-prefix counter. The hash chain (see `execution/README.md`) is fully
determined by this sequence, so two correct engines emit identical ledgers.
