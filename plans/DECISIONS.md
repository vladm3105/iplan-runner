# Architecture Decisions

ISO-8601 stamped, append-only. Newest decisions reference and may supersede
older ones (mark superseded entries, never delete).

---

### D-0001 - Repo is a hybrid spec + runtime - 2026-05-23

`aidoc-flow-iops-framework` is a **hybrid**: an engine-agnostic *contract* in
`framework/` (portable YAML + Markdown, no code) plus *reference runtimes* in
`platforms/` (real code), with a shared conformance suite in `tests/`. This
mirrors `aidoc-flow-framework` so we inherit "the same development approach."

### D-0002 - This repo is the execution/operations plane - 2026-05-23

SDD (`aidoc-flow-framework`) owns the **control plane**: BRD → … → IPLAN,
"done when committed + green." This framework owns the **execution/operations
plane** that begins at SDD's `EXEC-Ready (≥90)` gate: it consumes an approved
IPLAN and runs **IPLAN → Ledger → Gate → Monitor** (plan → append-only
execution evidence → independent completion proof → post-implementation
observation).

### D-0003 - Re-home the attached ledger plan under `framework/execution/` - 2026-05-23

The attached "IPLAN Ledger Implementation Plan" was authored against SDD's own
paths (`framework/layers/08_IPLAN/`, `platforms/hermes/...`,
`tests/conformance/`). We re-home its contract into `framework/execution/`
(not `framework/layers/08_IPLAN/`) because this repo is the *companion* to
SDD's Layer 8, not a re-declaration of it. A ledger binds to its source IPLAN
by `id` + `version` + `checksum`; we do **not** vendor SDD's IPLAN template and
take **no** hard dependency on the SDD repo.

### D-0004 - Development workflow mirrors SDD - 2026-05-23

Plan → review (≥2 passes) → implement → verify → land. Plans live in `plans/`
(start from `plans/PLAN-TEMPLATE.md`). Conformance must stay green; never weaken
a check to make it pass. One logical change per commit, conventional prefix.

### D-0005 - Per-engine platforms - 2026-05-23

`platforms/` holds one runtime per AI execution engine: `platforms/hermes/`
(MCP-server engine), `platforms/claude/` (Claude Code engine), and later
`platforms/codex/`, `platforms/vertexai/`, … All implement the same
engine-agnostic contract. **Slice 1 (PLAN-001) implements `hermes` + `claude`
fully**; other engines are follow-up plans.

### D-0006 - Monitoring is OpenTelemetry-based - 2026-05-23

Post-implementation monitoring uses OpenTelemetry (traces + metrics + logs via
OTLP) — exporter-agnostic, no vendor lock-in. `framework/monitoring/` defines
the manifest/SLO/signal contract; the runtime wires the OTel SDK and evaluates
SLOs. Health/readiness/startup probe shapes are adapted from the legacy
`aiops_framework` Cloud Run sample.

### D-0007 - Shared `core/` library; relaxed engine isolation - 2026-05-23

Because slice 1 ships **two** full engines, we resolve the shared-code question
now. We introduce a top-level **`core/` package (`iops_core`)** holding the
engine-agnostic logic: append-only ledger store, hash-chaining, isolation
enforcement, validators (ledger/chain/audit), the gate runner, audit-report
generation, OTel monitoring helpers, and shared CLI commands. Platforms depend
on `iops_core`; each adds only its engine-specific adapter (transport,
execution dispatch, instrumentation wiring).

This is a **deliberate divergence** from SDD's strict "platforms share only the
spec, no shared code" rule. Our engine-isolation conformance test is relaxed to:
*no platform imports another platform's package; platforms may import
`iops_core` and the `framework/` spec.* Rationale: an append-only,
hash-chained, auditable ledger must not exist as four divergent copies — that
would defeat the audit guarantees the framework exists to provide.

### D-0008 - Append-only, hash-chained, isolation-scoped ledger - 2026-05-23

The execution ledger is append-only; corrections are new compensating
transactions. The execution log is hash-chained (`sequence` +
`previous_event_hash` + `event_hash`). Every transaction is bound to an
isolation scope (`client_id` / `project_id` / `task_id`) and touched paths must
fall inside declared `allowed_roots`. Task transactions follow Saga-lite
semantics (forward action, compensation, idempotency key, timeout, escalation).
Inherited from the attached plan.

### D-0009 - Validation error-code namespaces - 2026-05-23

Reuse the attached plan's codes: `IPLAN-007` (ledger), `IPLAN-008` (chain
ledger), `IPLAN-009` (audit report). Add `MON-001` (monitoring manifest) and
`ENG-001` (engine-adapter conformance). Validators are deterministic
(dict-shape + regex), no LLM, no I/O — pure functions over parsed data.

### D-0010 - Python 3.11+ runtime - 2026-05-23

The container ships Python 3.11.15. Target Python ≥3.11 (SDD's Hermes targets
≥3.12, but the validator code uses only `dict[str,...]` / `list[...]` builtin
generics available in 3.11). Each platform declares `FRAMEWORK_SPEC_VERSION`
equal to `framework/VERSION`, enforced by conformance.
