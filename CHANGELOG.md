# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
