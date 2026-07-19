# TODO

Remaining work toward `v1.0.0` and beyond. Narrative + rationale live in
`ROADMAP.md`; decisions in `plans/DECISIONS.md`. Done phases: 1–9
(`v0.1.0` → `v0.9.0`).

## Pre-prod hardening — `plans/PLAN-025_preprod-hardening.md` (pre-GA)

Ready-for-build (verified-planning gate green: 17 citations, 4 passes). From the
2026-07-09 pre-prod review of the iplanic ↔ iplan-runner ↔ iplan-standard core.
Every code fix applies to **both** engines (`iplan_claude` + `iplan_hermes`).
**Independent / start now** — do not wait on the standard tag:

- [x] **B1 — clone-URL RCE (BLOCKER)** — scheme allow-list in `validation/payload_rules.py`
  (reject `ext::`/`file://`/leading-`-`); harden `vcs/git.py` argv (`--` after url; trailing
  `git checkout <ref> --` / rev-parse — NOT leading `--`). Add rejection tests + a test-only
  `file://` exemption for existing receiver fixtures. (Shipped PR #71.)
- [x] **B3 — reject-envelope wire bug (BLOCKER)** — `relay/reject.py` read `reason`; reorder
  integrity codes (`invalid_signature`/`schema_invalid`) **ahead** of the 403 branch. Cross-repo
  classification test vs iplanic's real `{"reason":…}` bodies. (Shipped PR #71.)
- [x] **M-wall** — measure + write `usage["wall_s"]`, add executor wall-timeout (hung task frees the slot). (Shipped PR #74.)
- [x] **M-ws / M-relay** — workspace GC after run settles; relay-DB retention/prune. (Shipped PR #73.)
- [ ] **M-crash** — auto re-drain tasks stuck in `running` on startup.
- [x] **M-body** — `try/except` the `Content-Length` parse (→400) + max body size (→413). (Shipped PR #72.)
- [x] **M-budget-parity** — add the pre-spend budget check to `HostRuntimeExecutor` (claude). (Shipped PR #72.)
- [ ] **M-rotation** — emitter key-rotation path (single static HMAC key today); rotation runbook.

**P2 — deployment contract (joint with iplanic PLAN-100 B2/B4):**

- [ ] **B2** — document `dispatch_token_id` MUST in `REMOTE_EXECUTOR_CONTRACT.md`.
- [ ] **B4** — contribute the runner half of the deployment-contract doc (static-token mode; key binding).

**P4/P6 — blocks on iplan-standard PLAN-0001 tagging `iplan/v0.5.0`:**

- [ ] **S4** — re-pin `iplan/v0.1.0` → `v0.5.0`; **decide L1 per PLAN-0001 M6** (single owner — do not
  decide independently); merge PLAN-024 gate or record opt-out citing M6.
- [ ] **S5** — wire `sync/check-drift.sh` into `pre_push_check.sh` / CI (it is orphaned today).
- [ ] **M-taskschema** — vendor `task.schema.json` + a runner-side conformance test (unenforced today).
- [ ] **INT-1** — cross-repo integration harness (joint w/ iplanic) — real dispatch→execute→ingest→project loop.

**P5 — docs/hygiene:** renumber the duplicate `PLAN-023` file + reconcile the `PLAN-024` collision;
refresh stale `plans/HANDOFF.md` (executed by PLAN-026 PR-2); document the `PYTHONPATH`/`pip install -e`
test-run requirement.

## Docs consistency & reference — `plans/PLAN-026_docs-consistency-and-reference.md`

From the 2026-07-19 three-lens docs review (accuracy / consistency / coverage):
~25 verified discrepancies + 5 HIGH reference gaps. Gate green (58 citations,
4 passes, 3 independent). PR slicing + the PLAN-026 self-ledger re-ground rules
live in the plan — follow them exactly (pre-commit `--all-files` gates every
plan on every PR).

- [ ] **PR-1 (W1a)** — PLAN-024/025 status headers + PLAN-024 HANDOFF-citation repoint (PLAN-018 untouched).
- [ ] **PR-2 (W1b)** — rewrite `plans/HANDOFF.md` (OPS-0062 pointer; retain `aidoc-flow-iplanic`); delete root `HANDOFF.md`; re-ground rows 13–15/18.
- [ ] **PR-3 (W2)** — ROADMAP refresh (header → v0.14.0; phases 2–10 → done; drop "no CI" / G13 / dead branch); re-ground rows 6–10.
- [ ] **PR-4 (W3)** — README (`receiver.executor` per-engine matrix; `iplanic.sync.enabled`; `docs/` row) + CLAUDE.md Unified-CI state; re-ground rows 11–12/30/34.
- [ ] **PR-5a (W4)** — SECURITY_REVIEW re-version (3× `v1.0.0` → 0.14.0) + GETTING_STARTED snippet self-contained / public signing-config path; re-ground rows 19/32–33.
- [ ] **PR-5b (W4)** — IPLAN-ECOSYSTEM: PLAN-013 is DONE; "not wired" corrected; mirror-divergence note (keep `aidoc-flow-iplanic`); re-ground rows 24–25/27.
- [ ] **PR-6 (W5)** — engine `VERSION`/`__version__` 0.13.0 → 0.14.0; fix CHANGELOG:12 script path; re-ground row 21.
- [ ] **PR-7 (W6a)** — `docs/CLI.md` (17 verbs + exit codes) + truthful `CONFIG_CONTRACT.md` rewrite (real keys, Reserved section, env-var table).
- [ ] **PR-8 (W6b)** — `docs/OPERATIONS.md` (receiver + sync how-to, example config) + REMOTE_EXECUTOR_CONTRACT `413`/`404` rows.
- [ ] **PR-9 (W6c)** — `docs/README.md` index + `framework/README.md` table (7 missing dirs) + README index link + CHANGELOG.
- [ ] **PR-10** — PLAN-026 Status → DONE + TODO close-out.

**Docs backlog (deferred from PLAN-026 — surplus scope, not planned):**
generated Python API reference; troubleshooting/FAQ; OTel runtime-provider
doc; release-process doc; platform-README dedup; D-0020 ecosystem-text
propagation (approval-gated upstream).

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
  (stdlib `sqlite3`, no new dep), outbox-shaped on `idempotency_key` so dead-letter +
  cursor-advance is one atomic transaction (iplanic-symmetric). The signed ledger
  stays a portable file. (DONE — built behind the unchanged store interface.)

## Inbound dispatch — A2A task receiver (PLAN-021 → PLAN-023 → PLAN-024)

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
- [x] **PLAN-022 — repo→workspace clone + executor seam** — **SHIPPED (D-0024,
  2026-07-05).** The receiver now **clones the dispatched repo** from
  `repository.{url,base_ref}` into a per-run `<workspace>/<run_id>/<task_id>`
  (`vcs/git.clone` + `receiver/service.provision_workspace`, `_slug` path-safe) and
  runs the task against that working copy; the executor became an injectable
  `ReceiverDeps.make_executor` factory (default still `MockExecutor`). Both engines.
  Deliberately clone-only — `ScriptedExecutor` is **not** the dispatched-task executor
  (it needs a pre-written `actions` spec a description-only todo never carries).
- [x] **PLAN-023 — config-selected receiver executor** — **SHIPPED (D-0025,
  2026-07-05).** `receiver.executor` (`mock` default / `host` claude / `api` hermes)
  picks the executor via the seam: `host` → `HostRuntimeExecutor(StubRuntimeClient)`
  (the budget+scope governor), `api` → `ApiExecutor(StubModelClient)` (model→actions).
  **Engine-specific** — each engine ships its own real-agent executor (D-0013), not a
  parity gap (spec parity = version + no-cross-import, not a source diff). Stub-only →
  fully CI-able; the **real** client adapters are the last piece (below).
- [ ] **PLAN-024 — real client adapters (integration-only).** The last live-execution
  gap: claude's real Claude Code hook `RuntimeClient` (only `StubRuntimeClient` exists) +
  hermes's real model client (`get_model_client(...)`, `[anthropic]` extra +
  credentials) — a **config-guarded swap of the stub** in the PLAN-023 factory, no
  other receiver change. Un-CI-able (needs a real runtime/API + credentials).
  - **DECISION B — the runtime (still open; pick when needed):** (a) **Claude Code
    CLI subprocess** — drive the real `claude` in the workspace; most faithful, needs
    the CLI + an API key in the runner env; hermes uses its own model client. (b)
    **Model API agent-loop** — an Anthropic/LiteLLM tool-loop doing edits;
    provider-pluggable, more code, no CLI dep. (c) **Generic subprocess I/O
    contract** — env/stdin task → stdout `RuntimeResult` JSON + workspace edits; most
    pluggable/testable, defers the actual agent to a configured command.
  - **Hardening follow-ons (separate plans, NOT the core):** auto re-drain on
    iplanic-outage recovery; in-flight crash-recovery + graceful-shutdown drain;
    mTLS/OIDC inbound auth + inbound signature-verify.
  - ⚠ **PLAN number collision:** `PLAN-024` was also reserved for the deferred L1
    intake-provenance-gate (unmerged branch) — pick distinct numbers when either lands.

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
