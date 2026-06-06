# Session Handoff

> Sessions run in ephemeral containers. **Only committed + pushed work
> survives.** Keep this file current before stopping or switching context.

## Current state - 2026-06-07

**Post-GA. Direction reframed: IOPS is a remote executor for Iplanic.**

### What's merged on `main` since GA

- `v1.0.0` GA (PR #8, PLAN-012 DONE): `examples/`, per-engine acceptance
  (`platforms/*/tests/test_acceptance.py`), `docs/SECURITY_REVIEW.md` +
  `SECURITY.md`, `docs/GETTING_STARTED.md`, contract-stability statement.
- `LICENSE` (Apache-2.0 canonical text) + `CONTRIBUTING.md` (PR #10). G13 done.
- pip-audit CI fix: `python -m pip install --upgrade pip` before audit so
  `PYSEC-2026-196` against the runner's bundled pip stops blocking all PRs.
- Plan-sizing rule (PR #11) encoded in `CLAUDE.md`, `plans/PLAN-TEMPLATE.md`
  (preamble + review-log instructions), and `CONTRIBUTING.md`. New plans must
  be sized to the problem; surplus surfaced by a review pass is speculative
  scope and must be cut.
- CI is fully wired and green: conformance + engine matrix (hermes/claude ×
  py3.11/3.12) + ruff + mypy --strict + pre-commit + pip-audit + gitleaks;
  CodeQL is advisory (`continue-on-error`) until code scanning is enabled on
  the repo. Dependabot weekly. All version markers at `1.0.0`.

### Strategic clarification (the architecture has three layers, not two)

```
SDD (aidoc-flow-framework)    -> authors the IPLAN (Layer 8 document)
Iplanic (aidoc-flow-iplanic)  -> hosted execution control plane:
                                 plan lifecycle, order, executor assignment,
                                 signed logs, evidence, knowledge graph.
                                 NOT the executor.
IOPS (this repo)              -> remote AI execution worker: hermes / claude
                                 connect to Iplanic over A2A + MCP + signed
                                 log-ingestion contracts.
```

Iplanic's IPLAN-STANDARD.md (read into a prior chat turn from the Iplanic repo
`docs/standards/IPLAN-STANDARD.md`) defines the plan + chain + remote-executor
model. **IOPS does NOT define the IPLAN handoff** — Iplanic does. IOPS's job
is to become a conformant remote executor.

When plugged into Iplanic: IOPS's `run_chain` is unused (Iplanic owns chain
orchestration), the engine completion gate becomes advisory (Iplanic owns the
completion gate), and the HMAC-signed ledger events become the basis for
signed log-ingestion upstream. Standalone IOPS still works unchanged.

### Concrete IOPS ↔ Iplanic mapping (from reading IPLAN-STANDARD.md)

| Concern | Iplanic standard | IOPS today |
|---|---|---|
| What IOPS consumes | Runtime task payload from `IPLAN-TASK-TEMPLATE.yaml` (binds intent to `task_id`/`run_id`/`executor_id`/lease/grants/`executor_work`/`executor_context`/reporting/failure-handling) | `iplan-intake` manifest — different shape; no payload-mode intake yet |
| ID granularity | `step_id` → `work_order_id` → `todo_id` + runtime `task_id` | Flat `task_id` |
| Context model | `executor_context` block: repo, workspace write scope, knowledge refs, MCP tools, secrets policy, forbidden paths; "executor must not infer missing context" | `isolation_scope.allowed_roots` + `Config.secrets` (subset) |
| Signed events | Streamed to Iplanic's signed log-ingestion endpoint | HMAC-signed in the engine ledger; no upstream ingestion |
| Completion authority | Iplanic — "executor self-reporting is not enough" | Engine-local gate (correct standalone; advisory when plugged in) |
| Lease / grants | Iplanic-minted (lease expiry, grants in payload) | Engine-local leases |
| Failure handling | Per-payload instructions from Iplanic | Engine saga (retry/compensate) |
| Chain orchestration | Iplanic owns it | IOPS has `run_chain` — unused when plugged into Iplanic |
| TMP-IPLAN | First-class artifact (source + return handoffs, `return_gate`) | Unsupported |
| Plan-vs-state separation | Approved plan canonical; must not be mutated; execution state separate | IOPS already separates intake from ledger ✓ |

What aligns well already: HMAC ledger → signed log-ingestion; hermes MCP tool
surface → MCP connector role; sandbox + allowed_roots → subset of
`executor_context`; per-task evidence runner; read-only-intake principle.

### Blocking — what the next session needs before drafting PLAN-013

The Iplanic repo (`vladm3105/aidoc-flow-iplanic`) is **private** to my GitHub
MCP scope and unauthenticated raw reads return 404. To draft a non-speculative
PLAN-013 (per the plan-sizing rule), the next session needs the **byte-level
contracts**, not just the prose standard:

1. `docs/standards/templates/IPLAN-TASK-TEMPLATE.yaml` — the actual runtime
   task-payload shape IOPS must consume. **Most important.**
2. `schemas/remote-executor.*` — executor registration contract.
3. `schemas/execution-event.*` — the signed event format IOPS must emit
   upstream.
4. `docs/PROTOCOLS.md` — concrete A2A / MCP / log-ingestion roles.
5. `docs/standards/IPLAN-DEFINITIONS.md` + `IPLAN-MANAGEMENT.md` — shared
   terminology and lifecycle rules (so we don't misuse `EXEC-Ready`, statuses,
   handoffs, comparison terms).

Options to unblock: paste these files into chat (fastest if Iplanic stays
private), or widen the Claude Code on the web environment's MCP repo scope to
include `vladm3105/aidoc-flow-iplanic`, or make the relevant Iplanic paths
public.

### Next step — PLAN-013 (narrowly scoped, per the plan-sizing rule)

Title: **Iplanic remote-executor conformance.**

In:

- (a) Payload-mode intake — consume Iplanic's task payload (`IPLAN-TASK-TEMPLATE.yaml`)
  in addition to the existing `iplan-intake` manifest; map payload IDs
  (`step_id`/`work_order_id`/`todo_id`) onto the engine's task model.
- (b) Signed log-ingestion — emit HMAC-signed engine ledger events to
  Iplanic's execution-event endpoint per the `execution-event` schema.
- (c) `executor_context` honoring — extend the sandbox to read forbidden
  paths, MCP-tool allowlist, and secrets policy from the payload rather than
  engine config; "executor must not infer missing context."
- (d) Conformance vectors at the boundary — golden vectors proving payload
  acceptance, event emission shape, and context enforcement.

Out (explicit speculative-scope cuts):

- TMP-IPLAN support (add later if needed).
- Reworking `run_chain` for Iplanic's tier/sequence chain model (Iplanic owns
  chain orchestration when plugged in; standalone `run_chain` stays).
- Full D-0015 auth wiring (already its own deferred item).
- Changes to SDD or Iplanic repos.

### Branch / PR pattern

Established and working: branch off latest `origin/main` (don't reuse
historical `claude/iplan-execution-framework-jc03k`), commit per task,
PR into `main`, subscribe via `mcp__github__subscribe_pr_activity` if needed.
CodeQL upload remains advisory until code scanning is enabled on the repo;
SARIF rejection there is expected and does not block merges.

## Current state - 2026-05-27

- Phase: **GA — `v1.0.0` (PLAN-012 DONE).** All 12 phases complete; the
  `framework/` contract is declared **stable under SemVer**.
- GA added: worked example (`examples/`), per-engine end-to-end acceptance
  (`platforms/*/tests/test_acceptance.py` — committed + green + monitored +
  signed on both engines), security review (`docs/SECURITY_REVIEW.md` +
  `SECURITY.md`), getting-started (`docs/GETTING_STARTED.md`), README + CHANGELOG
  `[1.0.0]`. Out (owner-deferred): LICENSE, packaging/distribution.
- Repo CI is committed (CI / CodeQL / security / pre-commit + Dependabot;
  PRs #1/#6/#7); pre-commit is enforced.
- Branch (historical): `claude/iplan-execution-framework-jc03k`.
- Phase 1 baseline: **PLAN-001 implemented** (SDD workflow: plan → 4 review
  passes → implement → verify → land).
- Repo decisions captured in `plans/DECISIONS.md` (D-0001..D-0012; D-0007
  superseded by D-0011).
- `plans/PLAN-001_iplan-execution-ledger-runtime.md` — **DONE** (`v0.1.0`).
- `plans/PLAN-002_iplan-intake-handover.md` — **DONE** (`v0.2.0`): IPLAN intake
  (normalize SDD IPLAN → `iplan-intake` manifest) + handover receipt contracts,
  per-engine readers/validators/builders, reader-parity conformance.
- `plans/PLAN-003_execution-core-run-loop.md` — **DONE** (`v0.3.0`): orchestrator
  + task state machine, pluggable `Executor` + `MockExecutor`, durable ledger
  persistence + status/query, gate-as-veto, `iops-<engine> run`/`status`, and
  scenario-vector conformance (projection + cross-engine differential).
- `plans/PLAN-004_effectors-evidence.md` — **DONE** (`v0.4.0`): sandbox/evidence
  contracts, pure `classify_path` (vector'd), sandboxed `apply_write`/
  `run_command`, evidence runner, secret redaction, and a `ScriptedExecutor`
  performing real effects; sandbox conformance.
- `plans/PLAN-005_saga-lease-runtime.md` — **DONE** (`v0.5.0`): saga runtime
  (bounded retry/backoff, idempotency, compensation undoing partial writes,
  escalation) + lease lifecycle (`can_acquire`/`renew`/state); saga scenarios +
  lease vectors.
- `plans/PLAN-006_landing-vcs.md` — **DONE** (`v0.6.0`): landing/VCS — `land()`
  commits a green+reconciled run to a git branch, records it in the ledger,
  `LEDGER.NOT_COMMITTED` (requires_landing-gated) lets the gate require
  committed + green; handover commit field; `run --land`.
- `plans/PLAN-007_security-ledger-integrity.md` — **DONE** (`v0.7.0`): security
  model + authenticated ledger (`sign_ledger`/`verify_ledger`, HMAC over canonical
  event), role-based `authorize`, realpath sandbox hardening; signing/authz
  vectors. Agent-first auth direction recorded in D-0015.
- `plans/PLAN-008_config-live-executors.md` — **DONE** (`v0.8.0`): config +
  secrets (`load_config`), resource governance (`Budget`/`check`), and the first
  live executors — hermes `ApiExecutor` (autonomous) + claude `HostRuntimeExecutor`
  (governor), the A/B divergence (D-0013); offline stub-tested, real clients
  integration-only.
- `plans/PLAN-009_hitl-operator-control.md` — **DONE** (`v0.9.0`): operator
  control (pause/abort between tasks + `run_state`), `resume` (paused/crashed via
  idempotency), `resolve_blocker` (approve/reject/override, operator-authorized +
  signed); pause/abort/resume/resolve CLI; `aborted` scenario.
- `plans/PLAN-010_monitoring-runtime.md` — **DONE** (`v0.10.0`): SLO-breach alert
  evaluation + issue record, probe HTTP server, live OTel metrics/logs (behind
  the extra), engine self-telemetry; alert conformance.
- `plans/PLAN-011_chain-orchestration.md` — **DONE** (`v0.11.0`): `run_chain`
  executes multi-IPLAN chains by composing the single-IPLAN loop (chain_order,
  upstream gating, control checkpoint, identity-free chain ledger); chain
  conformance. Next: **GA (`v1.0.0`)** — hardening, docs, worked example,
  packaging/release (see `TODO.md`).

## What landed (slice 1)

Hybrid spec + runtime with **strict engine isolation** (D-0011):

- `framework/` — engine-agnostic contract: execution ledger / verify-gate /
  chain / audit templates + protocol docs, OTel monitoring manifest,
  engine-adapter contract, registry, rule-ID catalog (20 rules), 24 golden
  vectors.
- `platforms/hermes/` + `platforms/claude/` — two fully self-contained engines
  (no shared code), each with ledger store + hash chain, validators, gate
  runner, audit generation, OTel-optional monitoring, SLO eval, CLI.
- `tests/conformance/` — vector replay + cross-engine differential + strict
  isolation + catalog coverage + spec parity.

## Verification (all green)

```
python -m unittest discover -s tests/conformance -v   # 14 passed
pytest platforms/hermes platforms/claude -q            # 57 passed
ruff check platforms                                   # clean
mypy --strict platforms/hermes/src platforms/claude/src  # clean
```

## Repo CI — committed (`.github/workflows/`)

CI now lives in the repo (the earlier `workflows`-permission block no longer
applies — the workflow files pushed cleanly). Modeled on the SDD repo's CI,
adapted to the two-engine strict-isolation layout:

- `ci.yml` — `conformance` (unittest suite: vectors + isolation + spec parity),
  `engines` (per-engine pytest matrix: hermes/claude × py3.11/3.12, via
  `python -m pytest`), and `lint` (`ruff check platforms` + `mypy --strict`).
- `codeql.yml` — Python SAST on push/PR to `main` + weekly schedule.
- `security.yml` — `pip-audit` dependency audit + `gitleaks` secret scan.
- `.github/dependabot.yml` — weekly pip (both engines + conformance) +
  github-actions version updates.

CodeQL is `main`-scoped, so it runs on PRs into `main` (not on feature-branch
pushes). Possible follow-up: a diff-aware spec-version bump gate like SDD's
`chg-gate.yml` (static parity is already covered by the conformance job).

## Backlog (post slice 1)

- `platforms/codex/`, `platforms/vertexai/` engines (own plans).
- Live Claude Code hook wiring for the `claude` engine.
- Fuller OTel provider (metrics/logs instruments) + OTLP collector wiring.
- Observability-driven issue loop (alert → issue).
- Optional: `LICENSE`, `CONTRIBUTING`, web-session `SessionStart` setup hook.
