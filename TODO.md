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
disabled; it can be enabled at any time. Builds on the D-4b transport
(`plans/PLAN-017` + D-0020).

- [ ] **Config-gated sync toggle** — an `iplanic` block in the engine config
  (`iplanic.sync.enabled` + endpoint + auth); **disabled by default**, so a
  fresh engine is standalone/offline. Flip it on at any time.
- [ ] **Mode 1 — online (with iplanic):** sync on. iplanic manages the lifecycle
  (dispatch, completion gate, evidence system-of-record); the engine relays
  signed events via the D-4b drain worker.
- [ ] **Mode 2 — standalone (offline), default:** sync off. Runs an approved
  IPLAN fully locally (signed ledger → gate → handover → monitor); iplanic is
  never contacted (individual plans, OSS, air-gapped, the Claude plugin).
- [ ] **On-demand sync command** — flush the locally-stored ledger / logs /
  evidence to iplanic from the durable cursor (`emit-events` → `POST /v1/events`),
  idempotent + resumable; canonical-JSON signing (D-0017) lets iplanic verify
  events produced offline.

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
