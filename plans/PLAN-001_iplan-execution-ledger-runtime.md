# IPLAN Execution Ledger + Runtime (hermes + claude) Implementation Plan

> Development plans follow the SDD workflow inherited from
> `aidoc-flow-framework`: **plan → review (≥2 passes) → implement → verify →
> land**. This plan must pass ≥2 review passes (see `## Review log`) and be
> approved before implementation begins.

**Goal:** Stand up `aidoc-flow-iops-framework` as the execution/operations-plane
companion to SDD: an engine-agnostic execution-ledger + verification-gate +
monitoring **contract** (`framework/`), a shared **core** runtime (`core/`),
and **two full reference engines** (`platforms/hermes`, `platforms/claude`) that
record, validate, gate, audit, and monitor IPLAN execution as append-only,
isolation-scoped, hash-chained transactions.

**Architecture:** Hybrid (D-0001). `framework/` holds the portable contract;
`core/` (`iops_core`) holds shared logic; `platforms/<engine>/` add only
engine-specific adapters and depend on `iops_core` (D-0007). Conformance in
`tests/` keeps every engine honest to the one spec.

**Tech Stack:** YAML contract templates; Python ≥3.11 (`iops_core` + platforms);
`pytest` (unit/integration); `unittest`-style conformance; OpenTelemetry SDK +
OTLP exporter; `ruff` + `mypy --strict`; Markdown governance docs.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-001 |
| Depends on | Attached "IPLAN Ledger Implementation Plan"; `aidoc-flow-framework` Layer 8 IPLAN spec (consumed, not modified); `plans/DECISIONS.md` D-0001..D-0010 |
| Status     | IN REVIEW - 2026-05-23 |
| Feeds      | Follow-up engine plans (`codex`, `vertexai`); multi-project control plane; observability-driven issue loop |

## Objective

Create the first repo-native execution/operations framework that treats agent
work as auditable transactions. The framework consumes an **approved** SDD IPLAN
(at the `EXEC-Ready ≥90` boundary, D-0002) and provides:

1. A portable **contract** for execution ledgers, verification gates, multi-IPLAN
   chains, audit reports, and post-implementation monitoring.
2. A shared **runtime** (`iops_core`) that creates/validates ledgers, enforces
   append-only hash-chained logging and isolation scopes, runs verification
   gates, generates audit/version-comparison reports, and wires OpenTelemetry
   monitoring.
3. **Two reference engines** (`hermes`, `claude`) that adapt the runtime to a
   specific AI execution engine, proving the contract is genuinely
   engine-agnostic.

The contract prevents silent task skips, weak completion claims, cross-task
interference, and cross-project/client leakage by requiring structured
transaction records, isolation boundaries, IPLAN version binding, leases,
evidence, verification gates, and chain-level reconciliation. This is the
attached IPLAN ledger plan, re-homed (D-0003) and extended with a runtime and
OTel monitoring.

## Scope

**In:**

1. Repo conventions mirroring SDD: `CLAUDE.md`, `README.md`, `CHANGELOG.md`,
   `VERSION`, `plans/`, `.gitignore`.
2. Engine-agnostic execution contract under `framework/execution/`: ledger,
   verify-gate, chain-ledger, and audit-report templates; agent-update,
   hook-integration, saga-execution, and ledger-isolation protocol docs.
3. Engine-agnostic monitoring contract under `framework/monitoring/`:
   OTel-aligned monitoring manifest template + post-implementation monitoring doc.
4. Engine-adapter contract (`framework/engines/ENGINE-ADAPTER-CONTRACT.md`) and
   the single-source-of-truth registry (`framework/registry/EXECUTION_REGISTRY.yaml`).
5. Shared `core/` package (`iops_core`): ledger store (append-only, hash-chain),
   isolation enforcement, ledger/chain/audit validators (re-homed), gate runner,
   audit-report generator, OTel monitoring helpers + SLO evaluation, shared CLI.
6. Two full engines: `platforms/hermes/` and `platforms/claude/`, each with
   `pyproject.toml`, `VERSION`, `FRAMEWORK_SPEC_VERSION`, an adapter implementing
   the engine-adapter contract, a console-script CLI, and platform tests.
7. Conformance suite: templates parse + match registry; registry integrity;
   relaxed engine-isolation; `FRAMEWORK_SPEC_VERSION == framework/VERSION`.
8. Unit + integration tests: validators, hash-chain, isolation, gate runner,
   audit generation, monitoring manifest validation, end-to-end ledger lifecycle.

**Out:**

1. Engines beyond `hermes` + `claude` (`codex`, `vertexai`, …) — follow-up plans.
2. A central multi-project database, dashboard, or web UI.
3. Automatic GitHub Issues / Projects synchronization.
4. Runtime distributed lease acquisition / cross-repository locking.
5. Automatic rollback of source changes (saga compensation records recovery +
   escalation only).
6. Live OTLP backend deployment (we emit OTel + ship a console/in-memory exporter
   for tests; pointing at a real collector is operator config).
7. Modifying the SDD repo (`aidoc-flow-framework`) in any way.

## Approach

The contract is additive and backward-compatible: an SDD IPLAN remains valid as
authored; this framework adds *companion* execution artifacts that bind to it by
`source_iplan` id + version + checksum (D-0003). No SDD template is vendored.

Three-part execution-control model, extended for ops (D-0002):

- `IPLAN` = planned execution contract (from SDD)
- `Ledger` = actual task/agent/evidence record (append-only, hash-chained)
- `Gate` = independent proof that completion is valid
- `Monitor` = post-implementation observation (OTel signals + SLOs)

**Shared core, not four copies (D-0007).** The append-only hash-chained ledger,
isolation enforcement, and validators live once in `iops_core`. Each engine adds
only its adapter: how it dispatches execution, where it records transactions
from, and how it wires instrumentation. The relaxed engine-isolation rule
(*platforms import `iops_core` + spec, never each other*) is enforced by
conformance so the divergence stays disciplined.

**Test-first where logic is non-trivial.** Core validators, the hash-chain, and
the gate runner are built TDD-style (failing test → implementation), inheriting
the attached plan's test cases (re-homed as standalone-document tests).

**Validators are deterministic** (D-0009): pure functions over parsed dicts,
accumulating `errors` / `warnings` / `passes`. We re-home only the ledger-side
codes (`IPLAN-007/008/009`); SDD's IPLAN structural codes (`SDD-IPLAN-001..006`)
stay in SDD because we consume already-approved IPLANs, not author them.

**Engine differences:**
- `hermes`: exposes core as MCP-server-style tools (`iops_validate_ledger`,
  `iops_run_gate`, `iops_audit_report`, `iops_monitor_check`) and dispatches
  execution via an API executor; console script `iops-hermes`.
- `claude`: a Claude Code adapter that implements `AGENT_UPDATE_PROTOCOL`
  (startup → lease → edit-recording → evidence → reconciliation) and records
  ledger transactions from observed local file edits / hook callbacks; console
  script `iops-claude`.

Both engines are "full" in the sense that matters: a complete adapter
implementing the engine-adapter contract, a working CLI, passing tests, and
spec-version parity. They are *thin by design* — all shared logic is in
`iops_core` (D-0007). `instrument()` differs only by OTel `Resource`
(`service.name = "iops-hermes"` vs `"iops-claude"`) before delegating to
`iops_core.monitoring.otel`.

**OpenTelemetry is an optional extra (R5).** `iops_core` defines a small
monitoring provider interface; the OTLP/OTel SDK lives behind
`iops_core[otel]`. When the extra is absent (e.g. offline container), a
console/no-op provider is used, so the contract, SLO evaluation, and all tests
remain runnable without network installs. SLO evaluation operates on collected
samples and is exporter-independent.

**Dev setup.** Packages use a `src/` layout and are installed editable for
tests/type-checking: `pip install -e ./core -e ./platforms/hermes -e
./platforms/claude` (plus `[dev]` extras for `pytest`/`ruff`/`mypy`).
Conformance itself needs only `pyyaml` (R12) and never imports the engines.

**Source-IPLAN binding is real, not nominal.** `iops_core.iplan.read_iplan_ref`
reads any SDD IPLAN-shaped YAML (read-only) and returns `{id, version,
last_updated, checksum}` where `checksum = "sha256:" + sha256(file_bytes)`. This
populates a ledger's `ledger_control.source_iplan*` fields without depending on
the SDD repo being present.

## File Structure

| Path | Responsibility |
|------|----------------|
| `CLAUDE.md` | Repo dev workflow + durable conventions (adapted from SDD). |
| `README.md` | What the framework is; control-plane vs execution-plane relationship to SDD. |
| `CHANGELOG.md` | Keep-a-changelog; `[Unreleased]`; tracks repo releases. |
| `.gitignore` | Python + tooling ignores. |
| `framework/VERSION` | **Single** spec-version source (`0.1.0`); registry + every engine must match it. |
| `framework/README.md` | IPLAN / Ledger / Gate / Monitor model overview. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | Single source of truth: contract artifacts, engines, error-code namespaces. |
| `framework/execution/IPLAN-LEDGER-TEMPLATE.yaml` | Ledger: task state, leases, evidence, blockers, reconciliation, saga journal, execution history, hash-chained execution log, audit snapshots. |
| `framework/execution/IPLAN-VERIFY-TEMPLATE.yaml` | Verification-gate rules + outcomes. |
| `framework/execution/IPLAN-CHAIN-LEDGER-TEMPLATE.yaml` | Ordered multi-IPLAN execution path + chain reconciliation. |
| `framework/execution/IPLAN-AUDIT-REPORT-TEMPLATE.yaml` | Execution history + version-comparison report. |
| `framework/execution/AGENT_UPDATE_PROTOCOL.md` | Mandatory agent update protocol. |
| `framework/execution/HOOK_INTEGRATION_POINTS.md` | Platform hook guardrails + authority limits. |
| `framework/execution/SAGA_EXECUTION_MODEL.md` | Saga-lite transactions, retries, compensation, escalation, journaling. |
| `framework/execution/LEDGER_ISOLATION_MODEL.md` | Task/project/client isolation boundaries. |
| `framework/execution/README.md` | Ledger semantics, status model, lease/evidence/reconciliation rules. |
| `framework/monitoring/MONITORING-MANIFEST-TEMPLATE.yaml` | OTel-aligned SLOs, signals (spans/metrics/logs), probes, alert rules, bound to `@iplan` + `@ledger`. |
| `framework/monitoring/POST_IMPLEMENTATION_MONITORING.md` | Post-impl monitoring model, OTel mapping, SLO evaluation, monitoring window. |
| `framework/monitoring/README.md` | Monitoring contract overview. |
| `framework/engines/ENGINE-ADAPTER-CONTRACT.md` | The interface every engine implements + capability declarations. |
| `core/pyproject.toml` | `iops_core` package metadata (Python ≥3.11). |
| `core/src/iops_core/iplan.py` | Read-only SDD IPLAN reference reader: `read_iplan_ref(path) -> {id, version, last_updated, checksum}`. |
| `core/src/iops_core/ledger/store.py` | Append-only ledger load/append; hash-chain (`sequence`/`previous_event_hash`/`event_hash`). |
| `core/src/iops_core/ledger/isolation.py` | Isolation-scope checks; touched-path ⊆ `allowed_roots`. |
| `core/src/iops_core/validation/ledger_rules.py` | `check_execution_ledger`, `run_iplan_ledger_validation_checks` (re-homed). |
| `core/src/iops_core/validation/chain_rules.py` | `run_iplan_chain_ledger_validation_checks` (re-homed). |
| `core/src/iops_core/validation/audit_rules.py` | `run_iplan_audit_report_validation_checks` (re-homed). |
| `core/src/iops_core/validation/monitoring_rules.py` | `run_monitoring_manifest_validation_checks` (`MON-001`). |
| `core/src/iops_core/gates/runner.py` | Verification-gate runner over a ledger + gate doc. |
| `core/src/iops_core/audit/report.py` | Audit-report + version-comparison generation. |
| `core/src/iops_core/monitoring/provider.py` | Monitoring provider interface + console/no-op default (no OTel dep). |
| `core/src/iops_core/monitoring/otel.py` | OTel tracer/meter/logger setup behind `iops_core[otel]` extra; exporter selection. |
| `core/src/iops_core/monitoring/slo.py` | SLO evaluation against collected samples (exporter-independent). |
| `core/src/iops_core/engine.py` | `EngineAdapter` Protocol/ABC (the engine-adapter contract in code). |
| `core/src/iops_core/cli.py` | Shared CLI commands (`ledger`, `gate`, `audit`, `monitor`); `main(argv)->int`. |
| `core/tests/fixtures/` | Valid sample ledger/chain/audit/monitoring docs + a sample IPLAN ref. |
| `core/tests/unit/` | Re-homed validator tests + hash-chain/isolation/gate/audit/monitoring unit tests. |
| `core/tests/integration/test_ledger_lifecycle.py` | End-to-end: read IPLAN ref → create ledger → record tasks → run gate → 2-plan chain reconcile → audit report. |
| `platforms/hermes/pyproject.toml` | `iops_hermes`; depends on `iops_core`; console script `iops-hermes`. |
| `platforms/hermes/VERSION`, `platforms/hermes/FRAMEWORK_SPEC_VERSION` | Engine version + spec parity. |
| `platforms/hermes/src/iops_hermes/adapter.py` | `HermesEngine(EngineAdapter)`; MCP-style tool surface + API-executor dispatch. |
| `platforms/hermes/src/iops_hermes/cli.py` | `iops-hermes` entry point (wraps `iops_core.cli`). |
| `platforms/hermes/README.md` | Hermes engine + ledger-verification expectations. |
| `platforms/hermes/tests/` | Hermes adapter unit tests. |
| `platforms/claude/pyproject.toml` | `iops_claude`; depends on `iops_core`; console script `iops-claude`. |
| `platforms/claude/VERSION`, `platforms/claude/FRAMEWORK_SPEC_VERSION` | Engine version + spec parity. |
| `platforms/claude/src/iops_claude/adapter.py` | `ClaudeEngine(EngineAdapter)`; AGENT_UPDATE_PROTOCOL via hooks/edit observation. |
| `platforms/claude/src/iops_claude/cli.py` | `iops-claude` entry point (wraps `iops_core.cli`). |
| `platforms/claude/README.md` | Claude engine + hook guardrail expectations. |
| `platforms/claude/tests/` | Claude adapter unit tests. |
| `tests/conformance/_spec.py` | Locate `framework/`, load registry. |
| `tests/conformance/test_contract.py` | Templates parse + metadata matches registry; required docs present. |
| `tests/conformance/test_registry.py` | Registry integrity (artifacts/engines/error codes resolve to files). |
| `tests/conformance/test_engines.py` | Relaxed engine isolation + `FRAMEWORK_SPEC_VERSION == framework/VERSION`. |
| `tests/conformance/requirements.txt` | `pyyaml`. |

## Step Sequence

### Task 1: Repo conventions & scaffolding

**Files:** Create `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `.gitignore`,
`framework/VERSION`, `framework/README.md`.

- [ ] **Step 1: Write `CLAUDE.md`** documenting: project purpose (execution/ops
  plane, D-0002); the plan → ≥2-review → implement → verify → land workflow;
  durable conventions (spec is the contract; conformance stays green; single
  source of truth = registry; engines import `iops_core` + spec only); session
  handoff via `plans/HANDOFF.md` ("only committed + pushed work survives").
- [ ] **Step 2: Write `README.md`** — what the framework is, the
  IPLAN/Ledger/Gate/Monitor model, the relationship to SDD, and a repo map.
- [ ] **Step 3: Write `framework/VERSION` (`0.1.0`)** — the single spec-version
  source; `CHANGELOG.md` (Keep-a-Changelog skeleton with `[Unreleased]`);
  `.gitignore` (Python, `.venv`, `__pycache__`, `*.egg-info`, `.pytest_cache`,
  `.mypy_cache`).
- [ ] **Step 4: Write `framework/README.md`** with the canonical model framing
  and links to the execution/monitoring/engines contract docs.
- [ ] **Step 5: Commit** — `git commit -m "chore: scaffold repo conventions"`.

### Task 2: Engine-agnostic execution contract

**Files:** Create the four `framework/execution/*.yaml` templates and four
`framework/execution/*.md` protocol docs + `framework/execution/README.md`.

- [ ] **Step 1: `IPLAN-LEDGER-TEMPLATE.yaml`** — re-home verbatim from the
  attached plan (Task 1, Step 1), changing only `metadata.tags`/`document_type`
  to suit this repo (`document_type: "iplan-ledger"`, drop `layer: 8`; add
  `framework: iops`). Keep all sections: `ledger_control` (with
  `source_iplan`/`source_iplan_version`/`source_iplan_last_updated`/
  `source_iplan_checksum`), `isolation_scope`, `task_ledger`, `agent_leases`,
  `execution_evidence`, `blockers`, `reconciliation`, `saga_journal`,
  `execution_history`, `execution_log` (hash-chained), `audit_snapshots`.
- [ ] **Step 2: `IPLAN-CHAIN-LEDGER-TEMPLATE.yaml`** — re-home from attached plan
  (Task 1, Step 2): `chain_control`, `iplan_chain`, `execution_tiers`,
  `cross_plan_leases`, `chain_gate_results`, `chain_reconciliation`.
- [ ] **Step 3: `IPLAN-AUDIT-REPORT-TEMPLATE.yaml`** — re-home from attached plan
  (Task 1, Step 3): `audit_control`, `version_scope`, `execution_summary`,
  `change_report`, `audit_findings`, `recommendation`.
- [ ] **Step 4: `IPLAN-VERIFY-TEMPLATE.yaml`** — re-home from attached plan
  (Task 1, Step 4): `gate_control`, `gate_rules` (GATE-LEDGER-001..005),
  `gate_results`.
- [ ] **Step 5: Protocol docs** — re-home `AGENT_UPDATE_PROTOCOL.md`,
  `HOOK_INTEGRATION_POINTS.md`, `SAGA_EXECUTION_MODEL.md`,
  `LEDGER_ISOLATION_MODEL.md` from attached plan (Task 3), removing SDD
  Layer-8-specific phrasing and pointing links at `framework/execution/` paths.
- [ ] **Step 6: `framework/execution/README.md`** — re-home the Layer 8 ledger
  semantics (attached plan Task 4 Steps 1–2): IPLAN/Ledger/Gate/Monitor model,
  task status model, lease/evidence/reconciliation rules, links to companions.
- [ ] **Step 7: Parse check** — `python -c "import glob,yaml;[yaml.safe_load(open(f)) for f in glob.glob('framework/execution/*.yaml')]"`.
- [ ] **Step 8: Commit** — `git commit -m "feat: add engine-agnostic execution ledger contract"`.

### Task 3: Monitoring contract

**Files:** Create `framework/monitoring/MONITORING-MANIFEST-TEMPLATE.yaml`,
`POST_IMPLEMENTATION_MONITORING.md`, `README.md`.

- [ ] **Step 1: `MONITORING-MANIFEST-TEMPLATE.yaml`** with sections:

  ```yaml
  metadata:
    schema_version: "1.0"
    document_type: "iplan-monitoring-manifest"
    framework: iops
    last_updated: "YYYY-MM-DD"
    tags: [monitoring-manifest, post-implementation, otel]
  monitor_control:
    monitor_id: "MON-IPLAN-NN"
    source_iplan: "@iplan: IPLAN-NN"
    source_ledger: "@ledger: LEDGER-IPLAN-NN"
    status: Draft
    monitoring_window:
      starts_at: "YYYY-MM-DDTHH:MM:SSZ"
      duration: "P7D"
  slos:
    - id: "SLO-001"
      name: "Availability"
      objective: 99.9
      unit: percent
      window: "30d"
      signal_ref: "availability_ratio"
  signals:
    otel:
      traces:
        - name: "iplan.task.execution"
          kind: internal
          attributes: ["iplan.id", "ledger.id", "task.id", "client.id", "project.id"]
      metrics:
        - name: "availability_ratio"
          instrument: gauge
          unit: "1"
        - name: "iplan.task.duration"
          instrument: histogram
          unit: "s"
      logs:
        - name: "iplan.execution.event"
          severity: INFO
  probes:
    health: "/healthz"
    readiness: "/readyz"
    startup: "/startupz"
  alert_rules:
    - id: "ALERT-001"
      when: "availability_ratio < 0.999"
      severity: error
      escalation_owner: "operator"
  ```

- [ ] **Step 2: `POST_IMPLEMENTATION_MONITORING.md`** — explain the monitoring
  model: monitoring binds to the same `@iplan`/`@ledger` identity (traceable
  observation), OTel signal mapping, SLO evaluation, the post-implementation
  window, and how alerts escalate (feeding a future observability-driven issue
  loop). Cite D-0006.
- [ ] **Step 3: `framework/monitoring/README.md`** — overview + links.
- [ ] **Step 4: Parse check** + **Commit** — `git commit -m "feat: add otel post-implementation monitoring contract"`.

### Task 4: Engine-adapter contract + execution registry

**Files:** Create `framework/engines/ENGINE-ADAPTER-CONTRACT.md`,
`framework/registry/EXECUTION_REGISTRY.yaml`.

- [ ] **Step 1: `ENGINE-ADAPTER-CONTRACT.md`** — define the interface each engine
  implements (mirrors `iops_core.engine.EngineAdapter`): `engine_id()`,
  `capabilities()`, `record_transaction(ledger, txn)`, `emit_execution_log(event)`,
  `run_gate(ledger, gate)`, `instrument(manifest)`. State the relaxed isolation
  rule (D-0007) and capability declaration format.
- [ ] **Step 2: `EXECUTION_REGISTRY.yaml`** — single source of truth:

  ```yaml
  metadata:
    framework: "AI Doc Flow IOps"
    spec_version: "0.1.0"
    template_policy: unified_yaml
  artifacts:
    - id: ledger
      template: "framework/execution/IPLAN-LEDGER-TEMPLATE.yaml"
      document_type: "iplan-ledger"
      error_prefix: "IPLAN-007"
    - id: verify
      template: "framework/execution/IPLAN-VERIFY-TEMPLATE.yaml"
      document_type: "iplan-verification-gate"
    - id: chain
      template: "framework/execution/IPLAN-CHAIN-LEDGER-TEMPLATE.yaml"
      document_type: "iplan-chain-ledger"
      error_prefix: "IPLAN-008"
    - id: audit
      template: "framework/execution/IPLAN-AUDIT-REPORT-TEMPLATE.yaml"
      document_type: "iplan-audit-report"
      error_prefix: "IPLAN-009"
    - id: monitoring
      template: "framework/monitoring/MONITORING-MANIFEST-TEMPLATE.yaml"
      document_type: "iplan-monitoring-manifest"
      error_prefix: "MON-001"
  protocol_docs:
    - "framework/execution/AGENT_UPDATE_PROTOCOL.md"
    - "framework/execution/HOOK_INTEGRATION_POINTS.md"
    - "framework/execution/SAGA_EXECUTION_MODEL.md"
    - "framework/execution/LEDGER_ISOLATION_MODEL.md"
    - "framework/engines/ENGINE-ADAPTER-CONTRACT.md"
  engines:
    - id: hermes
      package: iops_hermes
      path: "platforms/hermes"
    - id: claude
      package: iops_claude
      path: "platforms/claude"
  ```

- [ ] **Step 3: Parse check** + **Commit** — `git commit -m "feat: add engine-adapter contract and execution registry"`.

### Task 5: Shared core library (`iops_core`) — TDD

**Files:** Create `core/pyproject.toml`, `core/src/iops_core/**`, `core/tests/**`.

- [ ] **Step 1: `core/pyproject.toml`** — package `iops_core`, Python ≥3.11,
  base dep: `pyyaml`. Extras: `[otel]` = `opentelemetry-api`,
  `opentelemetry-sdk`, `opentelemetry-exporter-otlp`; `[dev]` = `pytest`,
  `ruff`, `mypy`. OTel is NOT a base dep (R5). Ship `py.typed` for `--strict`.
  Console entry not required here (engines own CLIs). Add `core/tests/fixtures/`
  with one valid ledger, chain, audit, monitoring manifest, and a minimal
  IPLAN-shaped YAML for `read_iplan_ref`.
- [ ] **Step 2: Write failing unit tests** in `core/tests/unit/` — re-home the
  attached plan's Task 5 Step 1 tests as standalone-document tests against:
  `run_iplan_ledger_validation_checks(ledger_data=...)` (evidence, acceptance,
  blocked decision owner, overlapping leases, reconciliation, source-version
  metadata, isolation scope, event isolation, touched-path-in-roots, hash-chain),
  `run_iplan_chain_ledger_validation_checks(chain_data=...)` (dependency order,
  upstream reconciliation, cross-plan lease overlap),
  `run_iplan_audit_report_validation_checks(audit_data=...)` (baseline/comparison
  identity + version/checksum). Add new tests: hash-chain `append_event`
  produces linked `event_hash`; isolation `touched_path` outside roots fails;
  `run_monitoring_manifest_validation_checks` MON-001 (source binding, SLO
  targets, signal types, probes). Run `pytest core -q` → expect failures.
- [ ] **Step 2b: Implement `iplan.py`** — `read_iplan_ref(path)` returns
  `{id, version, last_updated, checksum}`; `checksum = "sha256:" +
  sha256(file_bytes).hexdigest()`; `id`/`version`/`last_updated` pulled from the
  IPLAN's `document_control` when present (read-only; tolerant of missing fields).
- [ ] **Step 3: Implement `ledger/store.py`** — `load_ledger(path)`,
  `append_event(ledger, event)` computing `event_hash =
  sha256(f"{sequence}|{previous_event_hash}|{event_type}|{subject_id}|{at}")`,
  `verify_chain(ledger)`; append-only guarantee (never mutate prior events).
- [ ] **Step 4: Implement `ledger/isolation.py`** — `in_scope(path, allowed_roots)`,
  `assert_event_isolation(event)`.
- [ ] **Step 5: Implement `validation/{ledger,chain,audit,monitoring}_rules.py`**
  — re-home the attached plan's Task 5 Step 3–6 bodies (`check_execution_ledger`,
  `run_iplan_ledger_validation_checks`, `run_iplan_chain_ledger_validation_checks`,
  `run_iplan_audit_report_validation_checks`) into these modules unchanged except
  imports/namespace; add `run_monitoring_manifest_validation_checks` (MON-001).
- [ ] **Step 6: Implement `gates/runner.py`** — evaluate a verify-gate doc
  against a ledger doc by reusing the validators, mapping each
  `GATE-LEDGER-001..005` rule to the corresponding validator finding and
  returning per-rule pass/warn/error plus an overall gate status.
- [ ] **Step 7: Implement `audit/report.py`** — build an audit-report dict from a
  baseline + comparison ledger (version comparison); validate it via audit_rules.
- [ ] **Step 8: Implement `monitoring/provider.py` + `otel.py` + `slo.py`** —
  `provider.py` defines `MonitoringProvider` (start_span/record_metric/log) with a
  console/no-op default; `otel.py` provides an OTel-backed provider, imported
  lazily so absence of the `[otel]` extra degrades to the default (R5);
  `slo.py` `evaluate_slos(manifest, samples)` is exporter-independent (samples
  supplied as a dict/JSON; `monitor slo-check` reads a samples file).
- [ ] **Step 9: Implement `engine.py`** — `EngineAdapter` ABC/Protocol matching
  `ENGINE-ADAPTER-CONTRACT.md`.
- [ ] **Step 10: Implement `cli.py`** — argparse commands returning `int` exit
  codes: `ledger validate|show|append`, `gate run`, `audit report`, `monitor
  validate|slo-check`; `main(argv: list[str] | None = None) -> int`.
- [ ] **Step 11: Implement `tests/integration/test_ledger_lifecycle.py`** —
  read a fixture IPLAN ref → build a ledger (source bound) → append hash-chained
  events → `verify_chain` → run the verify-gate → build a 2-plan chain and
  reconcile → generate + validate an audit report. Asserts the happy path is
  gate-passing and the chain rejects out-of-order starts.
- [ ] **Step 12: Run `pytest core -q`, `ruff check core`, `mypy --strict
  core/src`** → all green. **Commit** — `git commit -m "feat: add iops_core ledger runtime, validators, gates, audit, monitoring"`.

### Task 6: Hermes engine

**Files:** `platforms/hermes/{pyproject.toml,VERSION,FRAMEWORK_SPEC_VERSION,README.md}`,
`platforms/hermes/src/iops_hermes/{__init__,adapter,cli}.py`, `platforms/hermes/tests/`.

- [ ] **Step 1: Package files** — `pyproject.toml` (`iops_hermes`, depends on
  `iops_core`, console script `iops-hermes = iops_hermes.cli:main`); `VERSION`
  (`0.1.0`); `FRAMEWORK_SPEC_VERSION` (`0.1.0`).
- [ ] **Step 2: `adapter.py`** — `HermesEngine(EngineAdapter)` exposing
  MCP-style tool functions (`iops_validate_ledger`, `iops_run_gate`,
  `iops_audit_report`, `iops_monitor_check`) delegating to `iops_core`; an
  API-executor dispatch stub (`run_executor(prompt)`) wrapped with execution-log
  emission; `instrument(manifest)` sets OTel `service.name="iops-hermes"` then
  delegates to `iops_core.monitoring`. No import from `iops_claude`.
- [ ] **Step 3: `cli.py`** — `iops-hermes` wrapping `iops_core.cli` + Hermes tools.
- [ ] **Step 4: `README.md`** — re-home attached plan Task 6 Step 2 (Hermes
  ledger-verification expectations).
- [ ] **Step 5: Tests** — adapter returns expected validator results on a known
  ledger; `engine_id() == "hermes"`. Run `pytest platforms/hermes -q`, `ruff`,
  `mypy --strict`.
- [ ] **Step 6: Commit** — `git commit -m "feat: add hermes execution engine"`.

### Task 7: Claude engine

**Files:** `platforms/claude/{pyproject.toml,VERSION,FRAMEWORK_SPEC_VERSION,README.md}`,
`platforms/claude/src/iops_claude/{__init__,adapter,cli}.py`, `platforms/claude/tests/`.

- [ ] **Step 1: Package files** — `pyproject.toml` (`iops_claude`, depends on
  `iops_core`, console script `iops-claude = iops_claude.cli:main`); `VERSION`;
  `FRAMEWORK_SPEC_VERSION`.
- [ ] **Step 2: `adapter.py`** — `ClaudeEngine(EngineAdapter)` implementing
  `AGENT_UPDATE_PROTOCOL`: `start_session()`, `acquire_lease()`,
  `record_touched_file()`, `record_evidence()`, `reconcile()`. Records ledger
  transactions from observed edits / hook callbacks via `iops_core.ledger.store`;
  `instrument(manifest)` sets OTel `service.name="iops-claude"` then delegates to
  `iops_core.monitoring`. No import from `iops_hermes`.
- [ ] **Step 3: `cli.py`** — `iops-claude` wrapping `iops_core.cli` + protocol helpers.
- [ ] **Step 4: `README.md`** — re-home attached plan Task 6 Step 1 (Claude Code
  hook guardrail expectations).
- [ ] **Step 5: Tests** — protocol round-trip produces a valid, gate-passing
  ledger; `engine_id() == "claude"`. Slice 1 exercises the adapter
  programmatically (live Claude Code hook wiring is a follow-up; the README
  documents how real hooks call these methods). Run `pytest platforms/claude
  -q`, `ruff`, `mypy --strict`.
- [ ] **Step 6: Commit** — `git commit -m "feat: add claude execution engine"`.

### Task 8: Conformance suite

**Files:** `tests/conformance/{_spec.py,test_contract.py,test_registry.py,test_engines.py,requirements.txt}`.

- [ ] **Step 1: `_spec.py`** — locate `framework/`, load `EXECUTION_REGISTRY.yaml`,
  expose `registry()`, `framework_root()`, `repo_root()`.
- [ ] **Step 2: `test_contract.py`** — every registry `artifacts[].template` is a
  file that parses as YAML and whose `metadata.document_type` matches the registry;
  every `protocol_docs[]` file exists.
- [ ] **Step 3: `test_registry.py`** — registry parses; artifact ids unique;
  error_prefixes unique; every referenced path exists; `metadata.spec_version`
  equals `framework/VERSION`.
- [ ] **Step 4: `test_engines.py`** — for each `engines[]`: its `path` exists,
  `FRAMEWORK_SPEC_VERSION` file equals `framework/VERSION`; **relaxed isolation** —
  grep each engine's `src/` for `import iops_<other-engine>` and assert none
  (importing `iops_core` is allowed).
- [ ] **Step 5: Run** `python -m unittest discover -s tests/conformance -v` → all
  pass. **Commit** — `git commit -m "test: add execution contract conformance suite"`.

### Task 9: Changelog, handoff, decisions finalize

**Files:** Modify `CHANGELOG.md`, `plans/HANDOFF.md`, `plans/PLAN-001_*.md` (status).

- [ ] **Step 1:** `CHANGELOG.md` `[Unreleased] → Added`: contract, core runtime,
  hermes + claude engines, OTel monitoring, conformance.
- [ ] **Step 2:** Update `plans/HANDOFF.md` with branch, completed tasks, next
  engines (`codex`, `vertexai`).
- [ ] **Step 3:** Set PLAN-001 `Status: DONE - <ISO>`.
- [ ] **Step 4: Full verification** (see below). **Commit** — `git commit -m "docs: record iops execution framework slice 1"`.

## Verification

> Nothing is "done" until these pass. Run from repo root.

```bash
# one-time dev setup (editable installs; [otel] optional)
pip install -e "./core[dev]" -e ./platforms/hermes -e ./platforms/claude

python -m unittest discover -s tests/conformance -v   # needs only pyyaml
pytest core platforms/hermes platforms/claude -q
ruff check core platforms
mypy --strict core/src platforms/hermes/src platforms/claude/src
git status --short --branch
```

Expected:

1. Conformance passes (contract parses + matches registry; engines spec-parity;
   no cross-engine imports).
2. Unit + integration tests pass (validators reject the attached plan's invalid
   cases; hash-chain links; gate runner + audit + monitoring validators behave).
3. Lint + strict types clean.
4. Two engines produce gate-passing ledgers from the same `iops_core`.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Re-homing drifts from the attached plan's validated rules. | Re-home validator bodies + test cases verbatim; only namespaces/paths change. |
| R2 | Contract leaks engine specifics. | Keep `framework/` code-free; engines import `iops_core`, never each other (conformance-enforced). |
| R3 | Shared `core` undermines engine isolation (vs SDD). | Relaxed-isolation conformance test (D-0007); documented divergence. |
| R4 | Two engines duplicate logic anyway. | Engines hold only adapters; all shared logic lives in `iops_core`. |
| R5 | OTel deps heavy / unavailable offline. | OTel is an optional `[otel]` extra behind a `MonitoringProvider` interface; absent it, a console/no-op provider is used. SLO eval + all tests run with only `pyyaml`. OTLP endpoint is operator config. |
| R6 | Python 3.11 vs SDD's 3.12. | Target 3.11 builtin generics only; no 3.12-only syntax (D-0010). |
| R7 | Ledger treated as self-attested. | Completed tasks require evidence + acceptance results; gate is the authority. |
| R8 | Append-only claim unauditable. | `sequence`/`previous_event_hash`/`event_hash` validated; `verify_chain` in tests. |
| R9 | Cross-project/client leakage. | Isolation scope + touched-path ⊆ `allowed_roots` validated per event. |
| R10 | `claude` CLI name clashes with Claude Code CLI. | Console script is `iops-claude`, package `iops_claude`. |
| R11 | Monitoring scope creep. | Slice 1 = manifest contract + OTel wiring + SLO eval only; no dashboards/collector deploy. |
| R12 | Conformance can't run without engine installs. | Conformance uses only `pyyaml` + filesystem/grep checks; no package import required. |

## Review log

> At least two passes before implementation. Each pass: re-read the whole plan,
> list findings, fold fixes back into the sections above. Stop when a pass finds
> nothing.

### Pass 1 - 2026-05-23

- Finding: integration test referenced no fixtures and the source-IPLAN binding
  was nominal. Change: added `core/src/iops_core/iplan.py` (`read_iplan_ref`,
  sha256 checksum), `core/tests/fixtures/`, and a Task 5 step to build them.
- Finding: OTel as a base dependency would make the runtime un-buildable in an
  offline container and couple tests to a network install. Change: moved OTel to
  an optional `[otel]` extra behind a `MonitoringProvider` interface with a
  console/no-op default; SLO eval + tests now need only `pyyaml` (R5 hardened).
- Finding: tests across packages can't import `iops_core` without installs.
  Change: added a "Dev setup" note + editable-install line in Verification.
- Finding: registry `spec_version` had no parity guard, risking drift from
  `framework/VERSION`. Change: added that assertion to `test_registry.py`.
- Finding: engine `instrument()` had no concrete per-engine behavior, making
  "two full engines" hand-wavy. Change: specified per-engine OTel
  `service.name` delegating to shared core (Tasks 6, 7).
- Finding: chain + audit contracts were only unit-tested. Change: extended the
  integration test to a 2-plan chain reconcile + audit-report generation.

### Pass 2 - 2026-05-23

- Finding: three version sources (root `VERSION`, `framework/VERSION`, registry
  `spec_version`) created a drift trap. Change: removed root `VERSION`;
  `framework/VERSION` is the single spec-version source, with registry + engines
  asserted equal to it.
- Finding: the gate runner glossed over mapping `GATE-LEDGER-NNN` rules to the
  `IPLAN-007`-coded validator findings. Change: specified the per-rule mapping
  and overall gate status in Task 5 Step 6.
- Finding: `claude` adapter "observes edits/hooks" overstated slice-1 reality.
  Change: clarified slice 1 exercises the adapter programmatically; live hook
  wiring is a follow-up, documented in the README.
- Finding: `mypy --strict` needs typing markers. Change: ship `py.typed`.
- Verification ↔ rules cross-check: each validator gate rule
  (`IPLAN-007/008/009`, `MON-001`, isolation, hash-chain) is exercised by a named
  unit test re-homed from the attached plan plus the new monitoring/chain/audit
  tests; the verification commands run that suite. No rule is left unverified and
  no check fires on a valid fixture (false-positive guard via the passing
  fixtures). No further findings.
