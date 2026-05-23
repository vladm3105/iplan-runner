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
