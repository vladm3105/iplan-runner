# Agent Update Protocol

The mandatory sequence every executing agent follows so the ledger is a faithful
append-only record. Engines implement this; the ledger is never edited by hand.

## Sequence

1. **Start session** — open (or load) the ledger for the source IPLAN; verify
   `ledger_control.source_iplan*` matches the IPLAN being executed.
2. **Acquire lease** — before working a task, record an `agent_leases` entry with
   `acquired_at` and `expires_at`. A task may not have two unreleased,
   time-overlapping leases (`LEDGER.LEASE_OVERLAP`).
3. **Record edits** — every material action appends an `execution_log` event
   (hash-chained) carrying `touched_paths`, `client_id`, `project_id`. Touched
   paths must fall within `isolation_scope.allowed_roots`
   (`ISOLATION.PATH_OUTSIDE_ROOTS`); event scope must match the ledger scope
   (`ISOLATION.EVENT_SCOPE_MISMATCH`).
4. **Record evidence** — a task may only move to `completed` with at least one
   `execution_evidence` entry (`LEDGER.EVIDENCE_REQUIRED`) and a passing
   `acceptance.result` (`LEDGER.ACCEPTANCE_WEAK`).
5. **Blockers** — moving a task to `blocked` requires a `decision_owner`
   (`LEDGER.BLOCKED_WITHOUT_OWNER`).
6. **Release lease** — set `released_at` when done with a task.
7. **Reconcile** — `reconciliation.allowed` may only be `true` when
   `pending_tasks == 0` and `open_blockers == 0`
   (`LEDGER.RECONCILE_INCONSISTENT`).

## Rules

- **Append-only.** Corrections are new entries / compensating saga transactions,
  never edits to prior entries.
- **No self-attestation.** Completion is proven by the verification gate, not by
  the agent asserting `completed`.
