# Handover Contract (the back door)

What the execution/operations plane publishes back toward the control plane when
a ledger reaches a terminal state. The `iplan-handover-receipt` is the closing
artifact of an execution run.

## Semantics

- A receipt binds `source_iplan` + `ledger_ref` + `gate_status` (+ optional
  `audit_report_ref`) and records the terminal `result`.
- `result.status`:
  - `completed` — the IPLAN executed to a gate-passing, reconciled end.
  - `aborted` — the run ended without completion (no completion claim is made).
- `created_at` is supplied by an **injected clock**; `receipt_id` is derived
  deterministically from `ledger_ref` — so independent engines produce identical
  receipts for identical inputs.

## Internal-consistency validation (`HANDOVER-001`)

The validator checks the receipt is **self-consistent only** — it does not read
the referenced ledger (that cross-check is the builder's responsibility, keeping
the validator pure).

| Rule | Triggers when |
|------|---------------|
| `HANDOVER.SOURCE_MISSING` | `source_iplan` or `ledger_ref` absent |
| `HANDOVER.STATUS_INVALID` | `result.status` not in {`completed`, `aborted`} |
| `HANDOVER.GATE_NOT_PASSED` | `status == completed` but `gate_status != passed` |
| `HANDOVER.NOT_RECONCILED` | `status == completed` but `reconciled != true` |

The `completed`-only rules do not apply to an `aborted` receipt, which is a valid
terminal state.

## Out of scope (later phases)

Transport / landing of the receipt (Phase 6), and signing/authentication of the
receipt (Phase 7). Phase 2 *produces and validates* the receipt only.
