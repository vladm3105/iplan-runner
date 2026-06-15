# Saga Execution Model

Task execution follows a **saga-lite** model: each task transaction has a
forward action and a compensation, is idempotent, and escalates on failure
rather than silently rolling back source code.

## Transaction

Each `saga_journal` entry:

| Field | Meaning |
|-------|---------|
| `txn_id` | Unique transaction id |
| `task_id` | Task this transaction belongs to |
| `action` | Forward action (e.g. `apply-edit`) |
| `compensation` | How to undo (e.g. `revert-edit`) — recorded, not auto-run |
| `idempotency_key` | Re-running with the same key is a no-op |
| `status` | `pending` → `committed` \| `compensated` |
| `timeout_s` | Max duration before the transaction is considered stuck |

## Lifecycle

1. **pending** — recorded before the action runs.
2. **committed** — action succeeded; evidence appended.
3. **compensated** — a later compensating transaction recorded the recovery.

## Failure handling

- On timeout or failure, the engine records a compensating transaction and a
  blocker with a `decision_owner` — it does **not** silently revert source code.
- Idempotency keys make retries safe: replaying a committed `idempotency_key`
  must not double-apply.
- Escalation (blocker + owner) is the terminal state for transactions that
  cannot be auto-recovered.

## Runtime state machine

The orchestrator runs each task transaction through this machine. Time and
`sleep` are **injected** (D-0014), so the flow is deterministic and testable.

```
                 success
   ┌────────────────────────────────▶ committed
pending ──execute──▶ failure ──retriable & attempt ≤ max_retries──▶ (backoff, retry)
                       │
                       └─ exhausted / non-retriable ─▶ compensate ─▶ compensated ─▶ escalate (blocker)
```

- **Idempotency.** Before executing, if a `committed` transaction already exists
  for the task's `idempotency_key`, execution is **skipped** (no-op within a run;
  the enabler for crash resume, Phase 9).
- **Attempts + retry.** `execute` is attempted up to `1 + max_retries` times. A
  result is retried only when it is a **`retriable`** failure and attempts remain;
  the attempt count is recorded on the transaction (`attempts`). Retries happen
  *inside* the execute step — they do **not** emit extra `execution_log` events.
- **Backoff.** Between attempts the engine waits `backoff_base · 2^(attempt-1)`
  via the injected `sleep` (a no-op in tests).
- **Timeout.** A reported timeout is treated as a **retriable** failure (real
  wall-clock interruption is later/best-effort).
- **Compensation.** If a task ultimately fails after applying partial effects,
  the engine **undoes** them (sandbox-gated; see `effectors`), appends a
  `compensation` execution-log event, and sets the transaction `compensated`.
  The append-only `file_edited` events remain — history stays truthful; the
  compensation event records the undo.
- **Escalation.** The task ends `blocked` with a blocker (`decision_owner`).

`max_retries` defaults to `0`: a single failure blocks immediately (the
PLAN-003/004 behavior).
