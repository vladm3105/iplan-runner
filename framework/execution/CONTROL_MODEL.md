# Control Model

How a human operator steers a run: pause / abort (between tasks), resolve
blockers (approve / reject / override), and resume a paused or crashed run.

## Run state

`ledger_control.run_state` tracks the **control/loop** lifecycle (distinct from
`handover_status`, which is done-ness):

| State | Meaning |
|-------|---------|
| `running` | the loop is processing tasks |
| `completed` | the loop ran to the end **uninterrupted** (tasks may still be blocked) |
| `paused` | control stopped the loop; **resumable** |
| `aborted` | control stopped the loop; terminal |

> `failure_blocks` has `run_state: completed` (the loop finished) but
> `handover_status: aborted` (tasks blocked) — the two are independent.

## Control checkpoint (between tasks)

The run loop consults an injected `control() -> "running" | "paused" |
"aborted"` **before each task**:

- `running` → process the task.
- `aborted` → stop; `run_state = aborted` (terminal); remaining tasks stay `pending`.
- `paused` → stop; `run_state = paused` (resumable); remaining tasks stay `pending`.

Default control is `running` (no stops). A task already in flight is **not**
interrupted — control is checked between tasks; the in-task bound is the saga
timeout (SAGA_EXECUTION_MODEL). The CLI builds `control` to read a store control
flag, so `pause`/`abort` from another process is seen at the next checkpoint.

## Blocker resolution

```
resolve_blocker(ledger, blocker_id, decision, actor)   # approve | reject | override
```

- **Authorized** (SECURITY_MODEL): the decision maps to an authz action —
  `override` → `"override"`, `approve`/`reject` → `"approve"` — and must pass
  `authorize(actor, action)` (the `operator` role); a denied actor is rejected.
- Records a `resolutions` entry `{blocker_id, decision, actor, at}` + a
  `resolution` execution-log event (append-only, signed).
- `override` removes the open blocker and resets the task to `pending` (so
  `resume` retries it); `reject` leaves it `blocked`; `approve` clears a
  pending-approval gate.

`override` is **accountable**: an operator-authorized, recorded, HMAC-signed
decision — not a silent bypass.

## Resume

```
resume(manifest, ledger, executor, *, clock, ids, sleep, control)
```

Continues an existing **persisted** ledger: the completed set is seeded from the
ledger, the loop is driven again, and committed tasks are **skipped**
(idempotency, SAGA_EXECUTION_MODEL). Pending tasks — including ones reset by
`override` — run; this is the same path for **resuming a pause** and **recovering
from a crash** (no special recovery code). A resumed run is itself
pausable/abortable via `control`.
