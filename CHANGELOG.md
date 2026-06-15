# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Renamed the engine packages `iops_hermes` → `iplan_hermes` and `iops_claude` →
  `iplan_claude`** (dist names `iplan-hermes`/`iplan-claude`; CLI entry points
  `iplan-hermes`/`iplan-claude`; `framework/registry/EXECUTION_REGISTRY.yaml` package
  keys updated so the conformance loader resolves both engines). Engine identities
  `hermes`/`claude`, the contract, the vectors, and the Iplanic wire surface are
  unchanged — rename only. **Dropped the former engineering codename.** (D-0019.)

### Added

- `security/iplanic_signing.py` (both engines): the `iplan-canonical-json` signer
  for Iplanic `execution-event` emission — RFC 8785 JCS + `sha256` + recursive
  drop-null, signed payload excluding `{signature, received_at}`, raw-byte HMAC
  key, and `ed25519` — making IOPS signatures byte-reproducible by Iplanic. The
  standalone authenticated-ledger signer is unchanged. (PLAN-014, D-0017.)
- Vendored Iplanic golden vectors (`framework/remote/iplanic-vectors/`,
  version-pinned) and a cross-engine conformance test reproducing them byte-for-byte
  (canonical bytes, `sha256`, and `hmac-sha256`/`ed25519` signature values).
- `rfc8785` and `cryptography` engine dependencies (for the Iplanic signer).
- Iplanic **remote-executor conformance** (PLAN-013, D-0016): a second intake front
  door `ingest_task_payload` maps the Iplanic task payload to the same
  `iplan-intake` manifest (run loop unchanged), and `to_execution_events` projects
  the signed ledger into Iplanic `execution-event`s (consuming the D-0017 signer).
  Both engines emit byte-identical events; conformance asserts the projection,
  required-field coverage, and the cross-engine differential.
- `REMOTE.PAYLOAD_*` payload validation (`validation/payload_rules.py`, category
  `REMOTE-001`) and the `framework/remote/` contract + vendored consumed-subset /
  emitted-required-field mirrors.
- Sandbox `classify_path` gains an optional `forbidden_paths` arg + `SANDBOX.FORBIDDEN`
  reason (checked after the positive jail; existing callers unchanged).
- CLI: `intake --payload <file>` and `emit-events <ledger> --payload <file>`.
- `REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT` payload validation (both engines): a task
  payload whose `executor_id` is present but not the Iplanic hash form
  `^exec:[a-z2-7]{16,}$` is rejected at intake, with a `reject_executor_id`
  conformance vector (PLAN-015, D-0018).
- Framework spec `1.1.0`; engines `0.12.0`.

### Changed

- Re-pinned the vendored Iplanic mirrors to `1.3-draft` / commit `fb5f46d` and
  conformed IOPS's `executor_id` to the hash form `exec:<base32(sha256(...))>`
  (Iplanic §2.1 / D-0031), regenerating the golden remote-conformance event
  signatures. The vendored canonicalization vectors are unchanged (byte-identical;
  Iplanic exempted them). Framework spec `1.1.0 → 1.2.0`; engines `0.12.0 → 0.13.0`.
  (PLAN-015, D-0018.)

## [1.0.0] - 2026-05-27

GA — consolidation and proof; no new contract or runtime. From this release the
`framework/` contract is **stable under SemVer** (breaking contract changes bump
the major version; the conformance suite is the gate).

### Added

- Worked end-to-end example (`examples/`): an approved SDD-IPLAN + action script
  (real writes + checks) + monitoring manifest, with a CLI walkthrough.
- Per-engine acceptance test (`platforms/*/tests/test_acceptance.py`) driving the
  full pipeline on the example to **committed + green + monitored + signed** on
  both engines (offline, deterministic).
- Security review (`docs/SECURITY_REVIEW.md`, per-threat mitigation + its test;
  residual risks named) + `SECURITY.md` disclosure policy.
- Getting-started guide (`docs/GETTING_STARTED.md`); README capability set +
  contract-stability statement.

### Notes

- **Out of scope** (owner-deferred, tracked in `TODO.md`): `LICENSE`,
  packaging / distribution. Residual: full auth wiring (D-0015), ledger schema
  migration (G10), live-executor integration coverage.

## [0.11.0] - 2026-05-24

### Added

- Chain orchestration runtime (`framework/execution/CHAIN_MODEL.md`): `chain_order`
  (stable topo), `run_chain` composing the single-IPLAN run loop with
  upstream-reconciled gating + a between-IPLAN control checkpoint, and an
  identity-free chain ledger (`build_chain_ledger`) + `ChainResult`.
- `iops-<engine> run-chain`; chain scenarios + cross-engine chain conformance.

## [0.10.0] - 2026-05-24

### Added

- Monitoring runtime (`framework/monitoring/MONITORING_RUNTIME.md`): SLO-breach-
  driven `evaluate_alerts` (via `alert_rules[].slo_ref`) + `build_issue` record
  (bound to `@iplan`/`@ledger`); alert conformance vectors.
- Probe HTTP server (`/healthz` `/readyz` `/startupz`); live OTel metrics/logs
  behind the `[otel]` extra (no-op default offline); engine self-telemetry
  (`emit_run_telemetry`), distinct from product monitoring.

## [0.9.0] - 2026-05-24

### Added

- Operator control (`framework/execution/CONTROL_MODEL.md`): an injected
  between-task `control` checkpoint + `ledger_control.run_state`
  (`running`/`paused`/`aborted`/`completed`).
- `resume(manifest, ledger, ...)` continues a paused or crashed run from its
  persisted ledger via idempotency (no special recovery path).
- `resolve_blocker(... decision, actor)` (`approve`/`reject`/`override`) —
  operator-authorized + recorded in the signed ledger; `override` resets the task
  to pending. `pause`/`abort`/`resume`/`resolve` CLI over the store.
- `aborted` control scenario + `run_state` in the scenario projection.

## [0.8.0] - 2026-05-24

### Added

- Config + secrets contract (`framework/config/CONFIG_CONTRACT.md`) +
  `load_config` (file + env merge; secrets/signing_key from env only).
- Resource governance (`framework/execution/RESOURCE_GOVERNANCE.md`): `Budget`
  (token/cost/wall-time) + pure `check`; `BUDGET.*` decisions + conformance.
- First **live executors** (A/B per D-0013): `hermes` `ApiExecutor` (autonomous:
  a model proposes typed actions, applied through the sandbox + budget) and
  `claude` `HostRuntimeExecutor` (governor: drive a host runtime, then govern its
  result against scope). Pluggable `ModelClient` / `RuntimeClient` with offline
  stubs; real clients import-guarded behind extras (integration-only).

## [0.7.0] - 2026-05-24

### Added

- Security model (`framework/security/SECURITY_MODEL.md`): authenticated ledger,
  layered authorization, agent-first identity (D-0015), untrusted-output
  principle, threat model.
- Authenticated ledger — `sign_ledger`/`verify_ledger` (HMAC-SHA256 over the
  canonical full event); `iops-<engine> verify --key`.
- Role-based `authorize(actor, action)` (L2 RBAC); `land(actor=...)` authorizes
  and signs when a key is configured.
- Sandbox realpath hardening (symlink-escape defense) in `apply_write`;
  `Config.signing_key` + `secrets_from_env`.
- Signing + authz golden vectors + cross-engine conformance.

## [0.6.0] - 2026-05-24

### Added

- Landing / VCS (`framework/vcs/LANDING_CONTRACT.md`): the "committed" half of
  done. VCS effector (`commit_all`/`head_sha`/`has_changes`) and a post-run
  `land()` that commits a green+reconciled run to a branch and records the commit
  in the ledger `vcs` section.
- `ledger_control.requires_landing` + `LEDGER.NOT_COMMITTED` (GATE-LEDGER-006):
  a landed ledger is complete only when committed + green.
- Handover receipt `commit` field; `iops-<engine> run --land --branch`.

## [0.5.0] - 2026-05-24

### Added

- Saga runtime: bounded retry with injected backoff, idempotency skip,
  timeout-as-failure, **compensation** that undoes partial writes, and escalation
  to a blocker (`SAGA_EXECUTION_MODEL.md` runtime state machine).
- Lease lifecycle + concurrency guard (`LEASE_MODEL.md`): `lease_state`,
  `can_acquire`, `renew`.
- `ExecutorResult.retriable`; `MockExecutor` per-task attempt sequences; injected
  `sleep`; `run(..., sleep=, max_retries=)`.
- Saga scenarios + lease decision vectors + cross-engine conformance.

## [0.4.0] - 2026-05-24

### Added

- Sandbox + evidence contracts (`framework/effectors/`).
- Pure path-jail decision `classify_path` (`SANDBOX.OK` / `OUTSIDE_ROOTS` /
  `ESCAPE`), enforced *before* effects; pinned by golden vectors + differential.
- Sandboxed effectors (`apply_write`, `run_command`), an evidence runner that
  runs acceptance checks, deterministic secret redaction, and a `ScriptedExecutor`
  that performs real effects from an action script.
- `iops-<engine> run --actions/--workspace` for real-effect runs.

## [0.3.0] - 2026-05-24

### Added

- Execution **run model** (`framework/execution/RUN_MODEL.md`) and **executor
  contract** (`framework/engines/EXECUTOR-CONTRACT.md`).
- Orchestrator + task state machine: drives an `iplan-intake` manifest through
  `pending → in_progress → completed | blocked` (dependency order, unmet-deps
  blocking), recording a hash-chained ledger.
- Pluggable `Executor` interface + deterministic `MockExecutor` (injected
  clock + id source).
- Durable, atomic, lock-guarded ledger persistence + a status/query surface.
- Gate-as-veto wired at the completion boundary; `iops-<engine> run` and
  `status` commands (CLI refactored to a `cli/` package).
- Scenario-vector conformance: per-engine projection + cross-engine differential.

## [0.2.0] - 2026-05-24

### Added

- IPLAN **intake** contract (`framework/intake/`): normalize an approved SDD
  IPLAN into a validated `iplan-intake` manifest (task graph) via a configurable
  field mapping; `INTAKE-001` rules.
- IPLAN **handover** contract (`framework/handover/`): `iplan-handover-receipt`
  published back toward the control plane; `HANDOVER-001` rules.
- Per-engine `ingest_iplan`, intake/handover validators, deterministic handover
  builder (injected clock), CLI `intake` / `handover` commands.
- Golden vectors for both new document types + a cross-engine **reader-parity**
  conformance test.

## [0.1.0]

### Added

- Planning artifacts and architecture decisions (D-0001..D-0012).
- Engine-agnostic execution contract (`framework/execution/`): ledger,
  verification-gate, chain-ledger, and audit-report templates + agent-update,
  hook-integration, saga, and isolation protocol docs.
- OpenTelemetry-aligned post-implementation monitoring contract
  (`framework/monitoring/`).
- Engine-adapter contract, execution registry, fine-grained rule-ID catalog,
  and 24 golden conformance vectors (`framework/`).
- Two fully self-contained reference engines under `platforms/`: `hermes`
  (MCP-server engine) and `claude` (Claude Code engine, AGENT_UPDATE_PROTOCOL),
  each with ledger store + hash chain, validators, gate runner, audit
  generation, OTel-optional monitoring, SLO evaluation, and a CLI.
- Conformance suite (`tests/conformance/`): vector replay, cross-engine
  differential, strict-isolation, rule-catalog coverage, and spec-version parity.
