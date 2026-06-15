# Task State Model

The lifecycle of a single task in an execution ledger. Engines implement this
identical state machine (pinned by conformance). **Run-level** orchestration
states (queued / running / paused / aborted) are defined later, with the run
loop (Phase 3) and operator controls (Phase 9); this document covers **task**
states only.

## States

| State | Meaning | Terminal |
|-------|---------|----------|
| `pending` | Declared by the IPLAN, not yet started | no |
| `in_progress` | An agent holds a lease and is working it | no |
| `completed` | Work done, evidence recorded, acceptance passing | yes |
| `blocked` | Cannot proceed; requires a `decision_owner` | no (resumable) |

## Transitions

```
pending ──▶ in_progress ──▶ completed
   ▲             │
   │             ▼
   └──────────  blocked  ◀── (from in_progress)
```

- `pending → in_progress` — a lease is acquired (no overlapping unreleased lease
  on the task; `LEDGER.LEASE_OVERLAP`).
- `in_progress → completed` — only with ≥1 evidence entry
  (`LEDGER.EVIDENCE_REQUIRED`) and `acceptance.result == "pass"`
  (`LEDGER.ACCEPTANCE_WEAK`). The **verification gate**, not the agent, is the
  authority on this transition (`GATE-LEDGER-*`).
- `in_progress → blocked` / `blocked → in_progress` — a blocked task must carry a
  `decision_owner` (`LEDGER.BLOCKED_WITHOUT_OWNER`); it resumes once the blocker
  is resolved.

## Invariants

- Every transition appends an `execution_history` entry and a hash-chained
  `execution_log` event — the record is **append-only**; corrections are new
  compensating entries (see `SAGA_EXECUTION_MODEL.md`).
- A ledger may set `reconciliation.allowed: true` only when no task is
  `pending`/`in_progress` and there are no open blockers
  (`LEDGER.RECONCILE_INCONSISTENT`).
- `completed` is the only success-terminal state; `blocked` is non-terminal and
  always resumable.
