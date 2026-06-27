# iplan-runner — Roadmap

| Field          | Value |
|----------------|-------|
| Project        | `iplan-runner` — the **execution / operations plane** |
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
of record* (record + verify) to a *running execution engine* (orchestrate →
execute → land → govern).

### What "done" means here

SDD's definition of done is **"committed + green."** The Phase 1 gate proves the
**ledger is well-formed** — it does *not* yet prove work **landed** or is
**green**. Closing that is explicit on this roadmap: **green** is delivered by
the evidence runner (Phase 4) and **committed** by landing/VCS integration
(Phase 6); from Phase 6 the gate can *require* both.

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
  validators) and — from Phase 3 — **scenario vectors** (stateful execution).
- **Pluggable execution (D-0013).** An engine is a **governance loop** with a
  pluggable `Executor` interface (`Mock` / `HostRuntime` / `Api`); the A-vs-B
  ("autonomous" vs "governor") choice is made per executor plugin, not globally.

## Cross-cutting (parallel track, not version-gated)

- **Repo CI** — run conformance + `pytest` + `ruff` + `mypy --strict` on every
  PR. *(Near-term; the repo currently has no CI.)*
- **Repo hygiene** — `LICENSE`, `CONTRIBUTING`, web-session `SessionStart` setup
  hook.

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

### Phase 2 — IPLAN intake, ingestion & handover  → `v0.2.0`

- **Intake (the front door):** where an approved IPLAN arrives, verification of
  the `EXEC-Ready ≥90` approval, and schema/version negotiation with SDD's
  IPLAN format (no hard dependency on the SDD repo).
- **Task-graph ingestion:** parse tasks, dependencies, acceptance criteria, and
  isolation scope out of the IPLAN (today only `read_iplan_ref`).
- **Handback (the back door):** where a gate-passing audit result is published
  back toward the control plane.
- **Thin config seam:** minimal config plumbing (paths, identifiers, endpoints)
  that later phases extend.
- Status: **planned** — `plans/PLAN-002`.

### Phase 3 — Execution core & run loop  → `v0.3.0`  *(keystone)*

- **Orchestrator** + task state machine (dep order; pending → in_progress →
  completed/blocked).
- The pluggable **`Executor` interface** + a deterministic **`MockExecutor`**
  (with injected clock + ID source so scenario vectors are reproducible).
- **State store**: durable atomic ledger persistence (lock + crash-safe append)
  **plus a status/query surface** (list active runs, inspect a run).
- **Gate-as-veto** wired at the completion boundary.
- `iops-<engine> run <iplan>` entrypoint.
- **Scenario-vector** conformance (op-sequence + mock executor → expected ledger).
- Status: **planned** — `plans/PLAN-003`.

### Phase 4 — Effectors & evidence  → `v0.4.0`

- Sandboxed action application — edits/commands **enforced** inside
  `allowed_roots` (not just validated after the fact). *(Baseline sandbox;
  hardening in Phase 7.)*
- **Evidence runner** — execute acceptance checks (tests/lint/commands) and
  capture results as evidence — the **"green"** half of done.
- Secret redaction in ledger + logs.
- Status: **planned** — `plans/PLAN-004`.

### Phase 5 — Saga & lease runtime  → `v0.5.0`

- Transaction **state machine**: idempotency, timeout, retry/backoff,
  compensation, escalation → blocker.
- **Lease** lifecycle: acquire / renew / expire / release + concurrency guard.
- Status: **planned** — `plans/PLAN-005`.

### Phase 6 — Landing & VCS integration  → `v0.6.0`

- Git **branch / commit / PR** flow — the **"committed"** half of done.
- The gate can now *require* "committed + green" before a ledger is complete.
- Status: **planned** — `plans/PLAN-006`.

### Phase 7 — Security & ledger integrity  → `v0.7.0`

- **Authn / authz** for who may run / approve / override.
- **Authenticated ledger** — signed / HMAC'd chain (the hash chain is
  tamper-*evident* but not *authenticated*; anyone can recompute it).
- Secret management, and **prompt-injection defense** on model/tool output.
- Sandbox hardening + threat model + security review.
- Status: **planned** — `plans/PLAN-007`.

### Phase 8 — Config, secrets & live executors  → `v0.8.0`  *(role-specific)*

- Full config contract (provider/model, API keys, OTLP endpoint, timeouts).
- `hermes` **`ApiExecutor`** (LiteLLM / Anthropic) — autonomous-style plugin.
- `claude` **`HostRuntimeExecutor`** + real Claude Code hooks — governor-style.
- **Resource governance** — token/cost budgets, rate limits, per-run timeouts.
- Status: **planned** — `plans/PLAN-008`. *(A/B chosen per engine here.)*

### Phase 9 — Human-in-the-loop & operator control  → `v0.9.0`

- **Approval / escalation routing** for blockers (surface → respond → resume).
- **Operator controls**: pause / resume / abort / override a live run, and
  **resume after crash** by rebuilding state from the append-only ledger.
- Status: **planned** — `plans/PLAN-009`.

### Phase 10 — Monitoring runtime  → `v0.10.0`

- Probe HTTP server (`/healthz` `/readyz` `/startupz` from the manifest).
- Live OTel metrics + logs (today the provider's metrics/logs are no-ops).
- Alert → issue loop.
- **Two scopes, kept distinct:** post-implementation monitoring of the *shipped
  product* (the manifest) vs *engine self-telemetry* (run progress, task/model
  latencies).
- Status: **planned** — `plans/PLAN-010`.

### Phase 11 — Chain orchestration runtime  → `v0.11.0`

- Execute multi-IPLAN chains (tiers, cross-plan leases, chain reconciliation) —
  today chains are only validated.
- Status: **done** — `plans/PLAN-011` (`v0.11.0`).

### Phase 12 — Execution engine feature-complete  → `v0.12.0`  (GA / `v1.0.0` deferred)

- End-to-end hardening, full security review, docs, and a worked example driving
  an IPLAN to a **committed + green**, gate-passing, monitored result on both
  engines — proven by the per-engine acceptance test.
- The `framework/` contract enters hardening but stays **pre-1.0 (`0.x`)** — it
  may change between minors while Phase-D work lands; **`v1.0.0` (GA)** is
  reserved for when the contract is frozen and declared stable under SemVer.
- **Packaging / release / distribution** and `LICENSE`: owner-deferred (tracked
  in `TODO.md`).
- Status: **done** — `plans/PLAN-012` (shipped as `v0.12.0`; contract now at
  `v0.14.0`).

## Tracked items

| Item | Note / decision | Revisit |
|------|-----------------|---------|
| **D-0011 — Strict engine isolation** | No shared runtime; engines share only the spec. | If maintaining N engines outweighs the isolation benefit. |
| **D-0012 — Parity via vectors** | Golden vectors for validators; scenario vectors (Phase 3) for stateful execution. | When a third engine lands. |
| **D-0013 — Pluggable executor** | Engine = governance loop + `Executor` interface. | Phase 8, first live executors. |
| **G9 — Scenario determinism** | Mock executor takes an injected clock + ID source. | Phase 3 design. |
| **G10 — Ledger schema migration** | Append-only + hash chain complicate migrating persisted ledgers across `framework/VERSION` bumps; no story yet. | First contract change after ledgers persist (Phase 3+). |
| **G13 — Repo hygiene** | `LICENSE`, `CONTRIBUTING` not yet added. | Parallel track, near-term. |

See `plans/DECISIONS.md` for full rationale (D-0001..D-0013) and `plans/` for
the development plans (`PLAN-001` complete; `PLAN-002` next).

## Planned capabilities (post-`v1.0`)

### Additional engines — `codex`, `vertexai`

- New self-contained `platforms/` runtimes, certified against the contract's
  vectors alone (no other engine required), per D-0012.

### Observability-driven issue loop

- Monitoring alerts (Phase 10) that breach an SLO open a tracked issue bound to
  the same `@iplan` / `@ledger` identity.

### Multi-tenant / multi-project control plane

- Coordinate ledgers across many `(client_id, project_id)` scopes with shared
  reconciliation and audit, building on the isolation model.

### CI / CD integration (user-facing)

- Run an engine as a step in the *user's* CI/CD to execute and gate IPLANs.

### Operating modes & on-demand iplanic sync

Two modes, selected by a **sync toggle** in the engine config (`iplanic.sync`,
**disabled by default**). **Built by D-4b** (`plans/PLAN-019`): the relay transport
+ the config-gated mode switch + the on-demand `sync` command. Operational-store
durability hardening is **built in D-4c** (`plans/PLAN-020`, D-0021): the relay's
cursor / dead-letter / identity live in a per-store SQLite DB (stdlib, no new dep),
outbox-shaped on `idempotency_key` so dead-letter + cursor-advance is one atomic,
iplanic-symmetric transaction; the signed ledger stays a portable file.

### Inbound dispatch — A2A task receiver

The **inbound** complement to the outbound relay: an opt-in `POST /v1/tasks`
receiver (config `receiver.enabled`, **disabled by default**, gated out of CI) so
iplanic can dispatch a task to a running engine over A2A instead of a file. **Built
by D-5a (wire slice)** (`plans/PLAN-021`, D-0022): mandatory-bearer door,
`(run_id, task_id)` idempotency (`accepted_task` table), deterministic run → relay
drain back, heartbeat liveness, `server` CLI verb. **Deferred → PLAN-022:** the live
executor (HostRuntime/API), repo → workspace clone from
`repository.{url,default_branch,base_ref}`, auto re-drain on outage, in-flight
crash-recovery + graceful-shutdown drain, and mTLS/OIDC inbound auth +
inbound signature-verify.

- **Standalone (offline) — default.** Sync off. The engine runs an approved
  IPLAN fully locally (signed ledger → gate → handover → monitor); iplanic is
  never contacted. The mode for individual plans, OSS users, air-gapped runs,
  and the Claude plugin.
- **Online (with iplanic).** Sync on. iplanic manages the lifecycle (dispatch,
  completion gate, evidence system-of-record); the engine relays signed events.
- **On-demand sync.** Either way, a standalone run can have sync enabled at any
  time (config flip) and flush its locally-stored ledger / logs / evidence to
  iplanic on request from the durable cursor — `iplan-canonical-json` signing
  (D-0017) lets iplanic verify events produced offline.
