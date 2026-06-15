# Rule-ID Catalog

Canonical, machine-readable source: [`rule-ids.yaml`](./rule-ids.yaml). This
document is the human-readable view. Every engine validator emits these IDs;
conformance compares the rule-ID set + status across engines (D-0012).

## Coarse categories

| Code | Scope |
|------|-------|
| `IPLAN-007` | Execution ledger validation |
| `IPLAN-008` | Chain ledger validation |
| `IPLAN-009` | Audit report validation |
| `MON-001` | Monitoring manifest validation |
| `INTAKE-001` | IPLAN intake manifest validation |
| `HANDOVER-001` | Handover receipt validation |

## Rules

| Rule ID | Category | Severity | Triggers when |
|---------|----------|----------|---------------|
| `LEDGER.SOURCE_VERSION_MISSING` | IPLAN-007 | error | source IPLAN id/version/checksum missing |
| `LEDGER.EVIDENCE_REQUIRED` | IPLAN-007 | error | completed task has no evidence |
| `LEDGER.ACCEPTANCE_WEAK` | IPLAN-007 | error | completed task acceptance not `pass` |
| `LEDGER.BLOCKED_WITHOUT_OWNER` | IPLAN-007 | error | blocked task / open blocker lacks decision owner |
| `LEDGER.LEASE_OVERLAP` | IPLAN-007 | error | two unreleased leases on a task overlap in time |
| `LEDGER.RECONCILE_INCONSISTENT` | IPLAN-007 | error | reconcile allowed while work/blockers remain |
| `ISOLATION.SCOPE_MISSING` | IPLAN-007 | error | client_id / project_id / allowed_roots missing |
| `ISOLATION.PATH_OUTSIDE_ROOTS` | IPLAN-007 | error | event touched a path outside allowed_roots |
| `ISOLATION.EVENT_SCOPE_MISMATCH` | IPLAN-007 | error | event client/project differs from ledger scope |
| `HASHCHAIN.BROKEN` | IPLAN-007 | error | execution_log hash chain inconsistent |
| `LEDGER.NOT_COMMITTED` | IPLAN-007 | error | requires_landing set but no vcs commit recorded |
| `CHAIN.ORDER_INVALID` | IPLAN-008 | error | IPLAN ordered at/before a dependency |
| `CHAIN.UPSTREAM_UNRECONCILED` | IPLAN-008 | error | depends on an unreconciled upstream |
| `CHAIN.LEASE_OVERLAP` | IPLAN-008 | error | cross-plan leases on one resource overlap |
| `AUDIT.IDENTITY_MISMATCH` | IPLAN-009 | error | baseline/comparison are different IPLANs |
| `AUDIT.VERSION_MISSING` | IPLAN-009 | error | baseline/comparison missing version or checksum |
| `AUDIT.VERSION_INCONSISTENT` | IPLAN-009 | error | same version but differing checksum |
| `MON.SOURCE_BINDING_MISSING` | MON-001 | error | source_iplan / source_ledger missing |
| `MON.SLO_MISSING_TARGET` | MON-001 | error | SLO has no objective |
| `MON.SIGNAL_REF_UNRESOLVED` | MON-001 | error | SLO signal_ref not a declared metric |
| `MON.PROBE_MISSING` | MON-001 | warning | health/readiness/startup probe absent |
| `INTAKE.SCHEMA_UNSUPPORTED` | INTAKE-001 | error | unsupported intake schema version |
| `INTAKE.SOURCE_MISSING` | INTAKE-001 | error | source IPLAN id/version/checksum absent |
| `INTAKE.APPROVAL_INSUFFICIENT` | INTAKE-001 | error | not approved or score < 90 |
| `INTAKE.SCOPE_MISSING` | INTAKE-001 | error | client/project/allowed_roots absent |
| `INTAKE.NO_TASKS` | INTAKE-001 | error | task_graph empty |
| `INTAKE.TASK_FIELDS_MISSING` | INTAKE-001 | error | task missing id/title/acceptance |
| `INTAKE.DEP_UNRESOLVED` | INTAKE-001 | error | depends_on references unknown task |
| `HANDOVER.SOURCE_MISSING` | HANDOVER-001 | error | source_iplan or ledger_ref absent |
| `HANDOVER.STATUS_INVALID` | HANDOVER-001 | error | result.status not completed/aborted |
| `HANDOVER.GATE_NOT_PASSED` | HANDOVER-001 | error | completed but gate not passed |
| `HANDOVER.NOT_RECONCILED` | HANDOVER-001 | error | completed but not reconciled |

## Status semantics

- `pass` — no findings.
- `warn` — only `warning`-severity findings.
- `fail` — at least one `error`-severity finding.
