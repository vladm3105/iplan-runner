# Lease Model

A lease scopes an agent to one task for a time window (see also
`LEDGER_ISOLATION_MODEL.md`). This document defines the lease **lifecycle** and
the **concurrency guard** the orchestrator applies before starting a task. The
decisions are pure functions of the lease records + an injected `now`, so they
are deterministic and parity-pinned (golden vectors + differential, D-0012).

## Lease record

```yaml
lease_id: "L1"
task_id: "T1"
agent_id: "<engine>"
acquired_at: "2026-05-24T10:00:00Z"
expires_at: "2026-05-24T11:00:00Z"   # null = no expiry
released_at: "2026-05-24T10:30:00Z"  # null = still held
```

## States

`lease_state(lease, now)`:

| State | When |
|-------|------|
| `released` | `released_at` is set |
| `expired` | not released and `expires_at` is set and `now > expires_at` |
| `active` | otherwise (held and within its window) |

## Concurrency guard

```
can_acquire(existing_leases, task_id, now) -> bool
```

False iff some lease in `existing_leases` for `task_id` is `active`. A new lease
may be acquired when every prior lease on the task is `released` or `expired`.

## Lifecycle operations

- **acquire** — only when `can_acquire` is true; append a lease with
  `acquired_at = now`.
- **renew** — extend `expires_at` (the lease must still be `active`).
- **expire** — implicit, by `now` passing `expires_at` (no mutation needed); the
  state is derived.
- **release** — set `released_at = now`.

## Scope

This phase covers **single-process** lease semantics. Distributed /
cross-process / cross-IPLAN lease coordination is the chain runtime (PLAN-007).
