# Intake Contract (the front door)

How an **approved** SDD IPLAN enters the execution/operations plane. SDD hands
over at the `EXEC-Ready ≥ 90` boundary; this framework **consumes a subset** of
the IPLAN, normalized into an `iplan-intake` manifest.

## No dependency on the SDD repo

We never import or pin SDD's IPLAN schema. Each engine's `ingest_iplan` reads an
SDD-IPLAN-shaped YAML and **maps** it to the `iplan-intake` manifest using a
documented, **configurable** field mapping (overridable in `config.py`). SDD
schema drift is absorbed by the mapping, not the engine core.

## Approval threshold

```
EXEC_READY_MIN = 90
```

A manifest is intake-ready only when `intake_control.approved` is `true` **and**
`intake_control.exec_ready_score >= 90` (`INTAKE.APPROVAL_INSUFFICIENT`).

## Default SDD → manifest field mapping

| Manifest field | Default SDD source |
|----------------|--------------------|
| `intake_control.source_iplan` | `document_control.iplan_id` |
| `intake_control.source_iplan_version` | `document_control.version` |
| `intake_control.source_iplan_checksum` | `"sha256:" + sha256(file_bytes)` (computed) |
| `intake_control.exec_ready_score` | `exec_ready.score` |
| `intake_control.approved` | `exec_ready.approved` |
| `isolation_scope` | `isolation_scope` (client/project/allowed_roots) |
| `task_graph[]` | `tasks[]` → `{task_id, title, depends_on, acceptance}` |

Engines may override these paths via `config.py` without touching core logic.

## Consumed subset (what we read)

`metadata.schema_version`, `intake_control.*`, `isolation_scope.*`,
`task_graph[].{task_id,title,depends_on,acceptance}`. Everything else in the
IPLAN is ignored by intake.

## Validation rules (`INTAKE-001`)

| Rule | Triggers when |
|------|---------------|
| `INTAKE.SCHEMA_UNSUPPORTED` | `metadata.schema_version` is not a supported version |
| `INTAKE.SOURCE_MISSING` | `source_iplan` / version / checksum absent |
| `INTAKE.APPROVAL_INSUFFICIENT` | `approved` not true, or `exec_ready_score < 90` |
| `INTAKE.SCOPE_MISSING` | `client_id` / `project_id` / `allowed_roots` absent |
| `INTAKE.NO_TASKS` | `task_graph` is empty |
| `INTAKE.TASK_FIELDS_MISSING` | a task lacks `task_id` / `title` / `acceptance` |
| `INTAKE.DEP_UNRESOLVED` | a `depends_on` entry references an unknown `task_id` |

The validator is pure and deterministic (no I/O, no clock). `ingest_iplan` is
also deterministic: the only derived field is the byte `sha256` checksum.
