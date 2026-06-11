# Iplanic Remote-Executor Contract (D-0016)

How IOPS acts as a **conformant remote executor for Iplanic**: it consumes
Iplanic's runtime **task payload** as a second intake front door, honors the
payload's `context_package` (incl. `forbidden_paths`), and emits **signed
`execution-event`s** in Iplanic's shape by projecting its own signed ledger.

This is **additive** (D-0016, mirrors D-0014): the standalone run loop, ledger,
gate, saga, and evidence runner are unchanged. Iplanic's schemas are **never
imported**; the consumed payload subset and the emitted event required-field list
are **vendored, version-pinned mirrors** under `framework/remote/`. Signing uses
the `iplan-canonical-json` signer (PLAN-014, D-0017), so emitted signatures are
byte-reproducible by Iplanic.

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

## Worked example

See `framework/conformance/remote/accept/` (`payload.yaml`, `ledger.yaml`,
`expect.yaml`) for a full payload → manifest → events projection, and
`remote/reject_context/` for the `REMOTE.PAYLOAD_*` findings.
