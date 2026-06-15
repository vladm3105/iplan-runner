# Execution Contract

The engine-agnostic contract for recording and verifying IPLAN execution.

## Artifacts

| Template | Document type | Purpose |
|----------|---------------|---------|
| `IPLAN-LEDGER-TEMPLATE.yaml` | `iplan-ledger` | Append-only, hash-chained record of one IPLAN's execution |
| `IPLAN-VERIFY-TEMPLATE.yaml` | `iplan-verification-gate` | Independent completion-proof rules over a ledger |
| `IPLAN-CHAIN-LEDGER-TEMPLATE.yaml` | `iplan-chain-ledger` | Ordered multi-IPLAN coordination + reconciliation |
| `IPLAN-AUDIT-REPORT-TEMPLATE.yaml` | `iplan-audit-report` | Version comparison between two ledgers of one IPLAN |

Protocol docs: `AGENT_UPDATE_PROTOCOL.md`, `HOOK_INTEGRATION_POINTS.md`,
`SAGA_EXECUTION_MODEL.md`, `LEDGER_ISOLATION_MODEL.md`.

## Task status model

```
pending ──▶ in_progress ──▶ completed
                │
                └────────▶ blocked  (requires decision_owner)
```

A task may move to `completed` only with ≥1 evidence entry and a passing
`acceptance.result`. The **verification gate**, not the ledger itself, is the
authority on completion.

## Lease / evidence / reconciliation rules

- **Leases** scope an agent to one task for a time window; no two unreleased
  leases on a task may overlap in time.
- **Evidence** is required for every completed task; acceptance must be `pass`.
- **Reconciliation** may be `allowed: true` only when there are no pending tasks
  and no open blockers.

## Hash chain

`execution_log` is append-only. For each event:

```
event_hash = sha256(f"{sequence}|{previous_event_hash}|{event_type}|{subject_id}|{at}")
```

The first event's `previous_event_hash` is `null`; each subsequent event chains
to the prior `event_hash`. A break is `HASHCHAIN.BROKEN`.

See `framework/conformance/rule-ids.yaml` for the full validation rule catalog.
