# Iplanic Remote-Executor Contract (D-0016)

How iplan-runner acts as a **conformant remote executor for Iplanic**: it consumes
Iplanic's runtime **task payload** as a second intake front door, honors the
payload's `context_package` (incl. `forbidden_paths`), and emits **signed
`execution-event`s** in Iplanic's shape by projecting its own signed ledger.

This is **additive** (D-0016, mirrors D-0014): the standalone run loop, ledger,
gate, saga, and evidence runner are unchanged. Iplanic's schemas are **never
imported**; the consumed payload subset and the emitted event required-field list
are **vendored, version-pinned mirrors** under `framework/remote/`. Signing uses
the `iplan-canonical-json` signer (PLAN-014, D-0017), so emitted signatures are
byte-reproducible by Iplanic.

The mirrors are pinned to **`iplan-standard@iplan/v0.1.0`** (https://github.com/vladm3105/aidoc-flow-iplan-standard). `executor_id`
must be the Iplanic self-certifying hash form **`^exec:[a-z2-7]{16,}$`**
(`exec:<base32(sha256(...))>`, Iplanic §2.1 / D-0031); a payload whose `executor_id`
is present but not in that form is rejected at intake
(`REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT`), since iplan-runner carries it into the signed,
emitted event (D-0018).

## Payload → `iplan-intake` manifest

`ingest_task_payload` reads the Iplanic task payload and maps it to the same
`iplan-intake` manifest the run loop already consumes, so no loop change is
needed. Extra manifest keys (`remote_execution`) are ignored by the loop.

| `iplan-intake` field | Iplanic payload source |
|---|---|
| `intake_control.source_iplan` | `iplan_id` |
| `intake_control.source_iplan_version` | `plan_version_id` |
| `intake_control.source_iplan_checksum` | `"sha256:" + sha256(payload bytes)` (computed) |
| `intake_control.approved` | `true` — **dispatch is the approval** (Iplanic only dispatches approved work; the `EXEC-Ready ≥ 90` gate is Iplanic's) |
| `intake_control.exec_ready_score` | `90` (asserted, not measured) |
| `isolation_scope.client_id` | `org_id` |
| `isolation_scope.project_id` | `project_id` |
| `isolation_scope.allowed_roots` | `["."]` (the repo workspace) |
| `isolation_scope.forbidden_paths` | `context_package.forbidden_paths` (additive) |
| `task_graph[]` | one entry per `work_order.todos[]`: `{task_id: todo_id, title: description, depends_on: [], acceptance: join(acceptance_criteria)}` |
| `remote_execution` (new block, loop-ignored) | `{task_id, run_id, step_id, work_order_id, executor_id, iplan_id, plan_version_id, org_id, project_id, protocol_plan_id, protocol_agent_id}` — the Iplanic identity, carried for event emission |

**Required context (no inference).** `ingest_task_payload` requires `org_id`,
`project_id`, `run_id`, `step_id`, `executor_id`, and a non-empty
`work_order.todos`; the `REMOTE.PAYLOAD_*` validator emits findings when any are
absent rather than defaulting them.

## Ledger → `execution-event` projection

`to_execution_events` walks the already-signed `execution_log` and emits one
Iplanic `execution-event` per ledger event, dropping the engine's `agent_id` and
using the payload's `executor_id`. Determinism: an injected `ids` source supplies
`event_id`/`trace_id`; `idempotency_key = f"{run_id}:{event_id}"`; `occurred_at`
is the ledger event's timestamp; `received_at = occurred_at` for the offline emit
(**Iplanic overwrites `received_at` on ingest**). The `signature` is produced by
the `iplan-canonical-json` signer and carries exactly `{key_id, algorithm,
value}`.

| Source in the ledger (real `execution_log` kinds) | Iplanic `event_type` | `status` |
|---|---|---|
| `task_started` | `task.started` | `running` |
| `file_edited` | `file.changed` | `running` |
| `task_completed` | `task.completed` | `succeeded` |
| `task_blocked` | `task.blocked` | `blocked` |
| `commit` (LANDING) | `artifact.created` | `running` |
| completed task `acceptance.result == pass` (derived) | `test.passed` | `running` |
| completed task `acceptance.result != pass` (derived) | `test.failed` | `running` |
| `compensation` | — (skip) | — |
| `resolution` | — (skip) | — |

`compensation` (saga undo) and `resolution` (blocker override) have no Iplanic
`event_type`, so they are deliberately skipped — never forced into a wrong
mapping. Event order follows ledger order; each task's derived `test.*` is emitted
immediately after that task's `task_completed`.

## Offline / transport boundary

Emission is **offline / in-memory**. A live HTTP POST to Iplanic's ingestion
endpoint is integration-only (behind an extra), exactly as live executors are
(PLAN-008). This plan does not ship a transport client.

## Inbound dispatch — task receiver (PLAN-021, D-0022)

The **outbound** half above is offline by default. The **inbound** half is an
opt-in HTTP door (`receiver.enabled`, stdlib `http.server`, gated out of CI) that
lets iplanic dispatch a task over A2A instead of a file:

```text
POST /v1/tasks
Authorization: Bearer <token>        # MANDATORY (constant-time compare)
Content-Type: application/json
<body = an iplanic task.schema.json payload>
```

| Response | Meaning |
| --- | --- |
| any `2xx` (`202 {task_id, run_id, status}`) | accepted — iplanic reads the **status only**; the body is debug-only |
| `400 schema_invalid` | body is not JSON / not an object / fails `validate_payload` / missing `task_id` |
| `401 unauthenticated` | absent or wrong bearer |
| `503 receiver_busy` | `max_parallel` runs already in flight (iplanic records a `DispatchError`, no attempt) |

**Prompt-ACK-then-background.** The handler durably accepts then ACKs `2xx`
immediately; the run executes on a daemon thread (a long run must not trip
iplanic's dispatch timeout, which maps to a `DispatchError`).

**Idempotent on `(run_id, task_id)`** (`task_id == step_id` recurs across chain
members, so the pair is the key). A row already `running`/terminal short-circuits
to `202` (`status: duplicate`); a fresh accept — or a crash-orphaned `accepted`
row whose run never started — runs. Two concurrent same-key POSTs both ACK, but an
atomic `accepted → running` claim lets exactly one run.

**Scope is the wire.** The dispatched `context_package.repository` **object**
(`{url, default_branch, base_ref}`) is rewritten to the configured `receiver`
workspace path before intake (`adapt_dispatched_task`); the run uses a
**deterministic** executor. The repo → workspace clone, the live executor, auto
re-drain, crash-recovery, and mTLS/OIDC inbound auth are **PLAN-022**.

### Cross-repo provisioning (two paired credentials)

The receiver authenticates iplanic, and iplanic verifies the receiver's signed
events — two shared credentials must be provisioned on both sides:

| Pairing | iplan-runner config | iplanic side |
| --- | --- | --- |
| **dispatch bearer** | `IOPS_RECEIVER_TOKEN` (`receiver.auth_env`) | the value iplanic resolves for the executor's `dispatch_token_id` (iplanic PLAN-048) |
| **event signature** | `receiver_key_id` = the registered `log_ingest_key_id`; `IOPS_SIGNING_KEY` = its secret | the secret iplanic resolves for that `log_ingest_key_id` (else every event `403`s) |

The receiver also runs a background heartbeat (`POST /executors/{id}/heartbeat`,
sending `X-Org-Id: receiver_org_id`) so iplanic keeps it dispatchable rather than
marking it `stale`. See iplanic `docs/runbooks/EXECUTOR-DISPATCH-SETUP.md`.

## Worked example

See `framework/conformance/remote/accept/` (`payload.yaml`, `ledger.yaml`,
`expect.yaml`) for a full payload → manifest → events projection, and
`remote/reject_context/` + `remote/reject_repository/` for the `REMOTE.PAYLOAD_*`
findings.
