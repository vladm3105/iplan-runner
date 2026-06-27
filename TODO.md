# TODO

Remaining work toward `v1.0.0` and beyond. Narrative + rationale live in
`ROADMAP.md`; decisions in `plans/DECISIONS.md`. Done phases: 1–9
(`v0.1.0` → `v0.9.0`).

## Numbered plans (the path to GA)

- [x] **PLAN-010 — Monitoring runtime** (`v0.10.0`): probe HTTP server, live OTel
  metrics/logs, alert → issue record, product-monitoring vs engine self-telemetry.
- [x] **PLAN-011 — Chain orchestration runtime** (`v0.11.0`): `run_chain` executes
  multi-IPLAN chains (order, upstream gating, chain reconciliation).
- [x] **PLAN-012 / GA** (`v1.0.0`): end-to-end hardening, security review, docs,
  worked example + per-engine acceptance (committed + green + monitored + signed
  on both engines); `framework/` contract declared stable under SemVer. LICENSE +
  packaging stay deferred (below).

## Parallel / cross-cutting (not version-gated)

- [x] **Repo CI** — `.github/workflows/`: CI (conformance + engine matrix +
  ruff/mypy), CodeQL (advisory until code scanning is enabled), pip-audit +
  gitleaks, and pre-commit; plus Dependabot. Merged via PRs #1 / #6 / #7.
- [x] **`LICENSE` + `CONTRIBUTING`** (G13): MIT (relicensed from Apache-2.0 in PLAN-018 G1).

## Operating modes & iplanic sync

Two modes, selected by a **sync toggle** in the engine config
(`iplanic.sync`, **off by default**). Standalone is offline mode with sync
disabled; it can be enabled at any time. **Delivered by D-4b**
(`plans/PLAN-019`, built on `plans/PLAN-017` + D-0020).

- [x] **Config-gated sync toggle** — an `iplanic` block in the engine config
  (`iplanic.sync.enabled` + endpoint + `token_env`); **disabled by default**, so a
  fresh engine is standalone/offline. Flip it on at any time. (D-4b Task 3.)
- [x] **Mode 1 — online (with iplanic):** sync on. iplanic manages the lifecycle
  (dispatch, completion gate, evidence system-of-record); the engine relays
  signed events via the D-4b drain worker (`relay/worker.py`). (D-4b Task 2.)
- [x] **Mode 2 — standalone (offline), default:** sync off. Runs an approved
  IPLAN fully locally (signed ledger → gate → handover → monitor); iplanic is
  never contacted (individual plans, OSS, air-gapped, the Claude plugin). A
  sync-disabled run opens no socket (asserted). (D-4b.)
- [x] **On-demand sync command** — `iplan-<engine> sync` flushes the locally-stored
  ledger to iplanic (`POST /v1/events`) from the durable cursor, at-least-once +
  resumable, with a dead-letter sink; canonical-JSON signing (D-0017) lets iplanic
  verify events produced offline. (D-4b Task 3.)
- [x] **D-4c — SQLite operational store** (`plans/PLAN-020`, D-0021): the relay
  cursor / dead-letter / identity now live in a per-store SQLite DB
  (stdlib `sqlite3`, no new dep), outbox-shaped on `idempotency_key` so dead-letter
  + cursor-advance is one atomic transaction (iplanic-symmetric). The signed ledger
  stays a portable file. (DONE — built behind the unchanged store interface.)

## Inbound dispatch — A2A task receiver (PLAN-021 → PLAN-022)

The outbound half (relay/sync) is done; the **inbound** half lets iplanic dispatch
a task to a running engine over A2A (`POST /v1/tasks`) instead of a file.

- [x] **PLAN-021 — inbound task receiver (wire slice)** — **BUILT (D-0022,
  2026-06-27).** Opt-in `POST /v1/tasks` (both engines, stdlib `http.server`, off by
  default, gated out of CI): mandatory constant-time bearer, extended
  `validate_payload` (`REMOTE.PAYLOAD_REPOSITORY_SHAPE`), `adapt_dispatched_task` +
  `ingest_task_payload_dict`, an `accepted_task` idempotency table (PK
  `(run_id, task_id)` + a `status` column; split durable-accept + atomic claim), a
  heartbeat thread, a `server` CLI verb, and a **deterministic** run through intake →
  orchestrator → relay back to iplanic — proven end-to-end against the in-process
  `/v1/events` fake. No iplanic PR remained (dispatcher-auth shipped, iplanic
  PLAN-048/D-0067); provisioning per iplanic `docs/runbooks/EXECUTOR-DISPATCH-SETUP.md`.
  256 offline + 12 gated tests, 26 conformance, ruff + `mypy --strict` clean.
- [ ] **PLAN-022 — receiver follow-on (deployment-shaped)** — the LIVE executor
  (HostRuntime/API), repo → workspace clone from
  `repository.{url,default_branch,base_ref}`, auto re-drain on iplanic-outage
  recovery, in-flight crash-recovery + graceful-shutdown drain, and mTLS/OIDC
  inbound auth + inbound signature-verify.

## Deferred / integration-only (not in CI)

- [ ] **Live executor integration tests** — real Anthropic/LiteLLM `ModelClient`
  (hermes) and real Claude Code `RuntimeClient` (claude); credential-gated.
- [ ] **Live Claude Code hook wiring** for the `claude` `HostRuntimeExecutor`.
- [ ] **Fuller OTel** — real metrics/logs instruments + an OTLP collector (PLAN-010
  starts this).
- [ ] **Full auth wiring (D-0015)** — OIDC/SPIFFE authn, the pluggable `Authorizer`
  PDP, and L3/L4 (ReBAC OpenFGA/SpiceDB, ABAC OPA/Cedar); agent-first M2M/A2A.

## Tracked items / risks

- [ ] **G10 — ledger schema migration** — a story for migrating persisted,
  hash-chained, signed ledgers when `framework/VERSION` changes a ledger field.
- [x] **G9 — scenario determinism** — injected clock/IDs (PLAN-003).
- [x] **G11 — product vs engine telemetry** — addressed by PLAN-010.

## Post-`v1.0`

- [ ] **`platforms/codex/`, `platforms/vertexai/`** engines (certified against the
  vectors alone).
- [ ] **Observability-driven issue loop** — post the PLAN-010 issue records to a
  tracker (GitHub Issues), bound to `@iplan`/`@ledger`.
- [ ] **Multi-tenant / multi-project control plane** — coordinate ledgers across
  many `(client_id, project_id)` scopes.
- [ ] **User-facing CI/CD integration** — run an engine as a step in users' CI.
