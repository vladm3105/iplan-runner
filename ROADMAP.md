# AI Doc Flow — IOps Framework Roadmap

| Field          | Value |
|----------------|-------|
| Project        | `aidoc-flow-iops-framework` — the **execution / operations plane** |
| Status         | **Slice 1 complete** — execution-ledger contract + two reference engines (`v0.1.0`) |
| Working branch | `claude/iplan-execution-framework-jc03k` |
| Companion      | `aidoc-flow-framework` — the **control plane** (BRD → … → IPLAN) |
| Created        | 2026-05-23 |

## Goal

Turn an **approved IPLAN** (handed over at SDD's `EXEC-Ready ≥90` boundary) into
audited, governed execution: **IPLAN → Ledger → Gate → Monitor**. One
engine-agnostic **contract** (`framework/`), many **fully self-contained
engines** (`platforms/<engine>/`) that share no code (strict isolation), kept
behaviorally identical by golden vectors. The journey runs from today's *system
of record* (record + verify) to a *running execution engine* (orchestrate +
execute + govern).

## Version streams

- **`framework/VERSION`** — the spec contract (SemVer); the single source of
  truth. The registry and every engine's `FRAMEWORK_SPEC_VERSION` track it.
- **`platforms/<engine>/VERSION`** — each engine carries its own independent
  SemVer stream.
- Roadmap phases advance the **spec** stream (`v0.1.0` → `v1.0.0`); engines
  release on their own cadence.

## Architecture commitments

- **Strict engine isolation (D-0011).** Engines import only the `framework/`
  spec — never each other. Code duplication is intentional.
- **Parity by vectors (D-0012).** Behavior is pinned by golden vectors (pure
  validators) and — from Phase 2 — **scenario vectors** (stateful execution).
- **Pluggable execution (D-0013).** An engine is a **governance loop** with a
  pluggable `Executor` interface (`Mock` / `HostRuntime` / `Api`); the A-vs-B
  ("autonomous" vs "governor") choice is made per executor plugin, not globally.

## Phases

### Phase 1 — Execution-ledger contract & reference engines  → `v0.1.0`

- **Contract (done):** `framework/execution` (ledger / verify-gate / chain /
  audit templates + protocol docs), `framework/monitoring` (OTel manifest),
  `framework/engines` (adapter contract), registry, rule-ID catalog (20 rules),
  24 golden vectors.
- **Engines (done):** `platforms/hermes` + `platforms/claude` — two
  self-contained runtimes (ledger store + hash chain, validators, gate runner,
  audit generation, OTel-optional monitoring, SLO eval, CLI).
- **Conformance (done):** vector replay + cross-engine differential + strict
  isolation + catalog coverage + spec parity.
- Status: **complete** (`v0.1.0`) — `plans/PLAN-001`.

### Phase 2 — Execution core & run loop  → `v0.2.0`

- IPLAN **task ingestion** (parse the task graph, not just id/version/checksum).
- **Orchestrator** + task state machine (dep order; pending → in_progress →
  completed/blocked).
- The pluggable **`Executor` interface** + a deterministic **`MockExecutor`**.
- **Durable** atomic ledger persistence (lock + crash-safe append).
- **Gate-as-veto** wired at the completion boundary.
- `iops-<engine> run <iplan>` entrypoint.
- **Scenario-vector** conformance (op-sequence + mock executor → expected ledger).
- Status: **planned** — `plans/PLAN-002` (keystone).

### Phase 3 — Effectors & evidence  → `v0.3.0`

- Sandboxed action application — edits/commands **enforced** inside
  `allowed_roots` (not just validated after the fact).
- **Evidence runner** — execute acceptance checks (tests/lint/commands) and
  capture results as evidence.
- Secret redaction in ledger + logs.
- Status: **planned** — `plans/PLAN-003`.

### Phase 4 — Saga & lease runtime  → `v0.4.0`

- Transaction **state machine**: idempotency, timeout, retry/backoff,
  compensation, escalation → blocker.
- **Lease** lifecycle: acquire / renew / expire / release + concurrency guard.
- Status: **planned** — `plans/PLAN-004`.

### Phase 5 — Config, secrets & live executors  → `v0.5.0`  *(role-specific)*

- Config contract (provider/model selection, API keys, OTLP endpoint, timeouts).
- `hermes` **`ApiExecutor`** (LiteLLM / Anthropic) — autonomous-style plugin.
- `claude` **`HostRuntimeExecutor`** + real Claude Code hooks — governor-style.
- Status: **planned** — `plans/PLAN-005`. *(A/B chosen per engine here.)*

### Phase 6 — Monitoring runtime  → `v0.6.0`

- Probe HTTP server (`/healthz` `/readyz` `/startupz` from the manifest).
- Live OTel metrics + logs (today the provider's metrics/logs are no-ops).
- Alert → issue loop.
- Status: **planned** — `plans/PLAN-006`.

### Phase 7 — Chain orchestration runtime  → `v0.7.0`

- Execute multi-IPLAN chains (tiers, cross-plan leases, chain reconciliation) —
  today chains are only validated.
- Status: **planned** — `plans/PLAN-007`.

### Phase 8 — Execution engine GA  → `v1.0.0`

- End-to-end hardening, security review, docs, and a real worked example
  driving an IPLAN to a gate-passing, monitored result on both engines.
- Status: **planned**.

## Tracked decisions

| Decision | Recorded | Revisit |
|----------|----------|---------|
| **D-0011 — Strict engine isolation** | No shared runtime; engines share only the spec; duplication intentional. | If maintenance cost of N engines outweighs isolation benefit. |
| **D-0012 — Parity via vectors** | Golden vectors for validators; scenario vectors (Phase 2) for stateful execution. | When a third engine lands — confirm scenario coverage scales. |
| **D-0013 — Pluggable executor** | Engine = governance loop + `Executor` interface (`Mock`/`HostRuntime`/`Api`). | Phase 5, when the first live executors are built. |

See `plans/DECISIONS.md` for full rationale (D-0001..D-0013) and `plans/` for
the development plans (`PLAN-001` complete; `PLAN-002` next).

## Planned capabilities (post-`v1.0`)

### Additional engines — `codex`, `vertexai`

- New self-contained `platforms/` runtimes, certified against the contract's
  vectors alone (no other engine required), per D-0012.

### Observability-driven issue loop

- Monitoring alerts (Phase 6) that breach an SLO open a tracked issue bound to
  the same `@iplan` / `@ledger` identity.

### Multi-tenant / multi-project control plane

- Coordinate ledgers across many `(client_id, project_id)` scopes with shared
  reconciliation and audit, building on the isolation model.

### CI / CD integration & crash recovery

- Run the engine as a CI step; resume an interrupted execution by rebuilding
  state from the append-only ledger.
