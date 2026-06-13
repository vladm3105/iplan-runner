# IPLAN Execution Ledger + Runtime (hermes + claude, strict isolation) Implementation Plan

> Development plans follow the SDD workflow inherited from
> `aidoc-flow-framework`: **plan → review (≥2 passes) → implement → verify →
> land**. This plan must pass ≥2 review passes (see `## Review log`) and be
> approved before implementation begins.

**Goal:** Stand up `iplan-runner` (engineering codename `iops-framework`) as the execution/operations-plane
companion to SDD: an engine-agnostic execution-ledger + verification-gate +
monitoring **contract** (`framework/`), and **two fully self-contained reference
engines** (`platforms/hermes`, `platforms/claude`) that each independently
record, validate, gate, audit, and monitor IPLAN execution. The engines share
**no code** (D-0011); their behavioral identity is guaranteed by **golden
conformance vectors** (D-0012).

**Architecture:** Hybrid (D-0001) with **strict engine isolation** (D-0011).
`framework/` holds the portable contract — including a canonical rule-ID catalog
and a golden-vector corpus. Each `platforms/<engine>/` is a complete, standalone
implementation that imports only the spec, never another engine. Conformance in
`tests/` replays the vectors against every engine and forbids cross-engine
imports.

**Tech Stack:** YAML contract templates + vectors; Python ≥3.11 (each engine,
independently); `pytest` (per-engine unit/integration); `unittest`-style
conformance (vector replay + isolation + parity); OpenTelemetry SDK + OTLP
behind an optional extra; `ruff` + `mypy --strict`; Markdown governance docs.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-001 |
| Depends on | Attached "IPLAN Ledger Implementation Plan"; `aidoc-flow-framework` Layer 8 IPLAN spec (consumed, not modified); `plans/DECISIONS.md` D-0001..D-0012 |
| Status     | DONE - 2026-05-23 |
| Feeds      | Follow-up engine plans (`codex`, `vertexai`); multi-project control plane; observability-driven issue loop |

## Objective

Create the first repo-native execution/operations framework that treats agent
work as auditable transactions. The framework consumes an **approved** SDD IPLAN
(at the `EXEC-Ready ≥90` boundary, D-0002) and provides:

1. A portable **contract** for execution ledgers, verification gates, multi-IPLAN
   chains, audit reports, and post-implementation monitoring — plus a **rule-ID
   catalog** and **golden vectors** that pin validation *behavior*, not just
   document shape.
2. **Two reference engines** (`hermes`, `claude`), each a complete standalone
   runtime that creates/validates ledgers, enforces append-only hash-chained
   logging and isolation scopes, runs verification gates, generates audit /
   version-comparison reports, and wires OpenTelemetry monitoring.

Strict isolation (D-0011) means the engines duplicate logic on purpose and can
evolve — or be reimplemented in other languages — independently, while the
golden vectors (D-0012) keep their verdicts identical. This prevents silent task
skips, weak completion claims, cross-task interference, and cross-project/client
leakage by requiring structured transaction records, isolation boundaries, IPLAN
version binding, leases, evidence, verification gates, and chain reconciliation.
This is the attached IPLAN ledger plan, re-homed (D-0003) and extended with
self-contained runtimes, OTel monitoring, and a parity harness.

## Scope

**In:**

1. Repo conventions mirroring SDD: `CLAUDE.md`, `README.md`, `CHANGELOG.md`,
   `framework/VERSION`, `.gitignore`, `plans/`.
2. Engine-agnostic execution contract under `framework/execution/`: ledger,
   verify-gate, chain-ledger, and audit-report templates; agent-update,
   hook-integration, saga-execution, and ledger-isolation protocol docs.
3. Engine-agnostic monitoring contract under `framework/monitoring/`:
   OTel-aligned monitoring manifest template + post-implementation monitoring doc.
4. Engine-adapter contract (`framework/engines/ENGINE-ADAPTER-CONTRACT.md`), the
   single-source-of-truth registry (`framework/registry/EXECUTION_REGISTRY.yaml`),
   the rule-ID catalog (`framework/conformance/rule-ids.yaml` + `RULE-IDS.md`).
5. Golden conformance vectors under `framework/conformance/vectors/`: valid +
   invalid ledger/chain/audit/monitoring documents, each with an `*.expect.yaml`
   (status + rule-ID set + severities), seeded from the attached plan's tests.
6. Two fully self-contained engines, `platforms/hermes/` and `platforms/claude/`,
   each with its own `pyproject.toml`, `VERSION`, `FRAMEWORK_SPEC_VERSION`, a
   complete runtime (ledger store, iplan reader, validators emitting rule IDs,
   gate runner, audit generator, monitoring provider + optional OTel, CLI), an
   adapter implementing the engine-adapter contract (incl. the uniform
   `validate(document)` entry point), and its own test suite.
7. Conformance suite: replays vectors against **each** engine (status + rule-ID
   parity); rule-ID catalog coverage; relaxed-free **strict** isolation (no
   cross-engine imports); `FRAMEWORK_SPEC_VERSION == framework/VERSION`;
   cross-engine differential agreement.

**Out:**

1. Engines beyond `hermes` + `claude` (`codex`, `vertexai`, …) — follow-up plans.
2. Any shared runtime library between engines (explicitly rejected, D-0011).
3. A central multi-project database, dashboard, or web UI.
4. Automatic GitHub Issues / Projects synchronization.
5. Runtime distributed lease acquisition / cross-repository locking.
6. Automatic rollback of source changes (saga compensation records recovery +
   escalation only).
7. Live OTLP backend deployment (engines emit OTel + ship a console/no-op
   provider; pointing at a collector is operator config).
8. Modifying the SDD repo (`aidoc-flow-framework`) in any way.

## Approach

The contract is additive and backward-compatible: an SDD IPLAN remains valid as
authored; this framework adds *companion* execution artifacts that bind to it by
`source_iplan` id + version + checksum (D-0003). No SDD template is vendored.

Execution-control model, extended for ops (D-0002): `IPLAN` (planned contract,
from SDD) → `Ledger` (append-only, hash-chained actuals) → `Gate` (independent
completion proof) → `Monitor` (post-implementation OTel signals + SLOs).

**Strict isolation, no shared code (D-0011).** Each engine is a complete,
standalone runtime. `hermes` and `claude` each carry their own ledger store,
validators, gate runner, audit generator, monitoring, and CLI. Neither imports
the other; both import only the `framework/` spec (as data). The duplication is
deliberate.

**Behavioral parity via golden vectors (D-0012).** The thing that keeps two
independent implementations honest is data, not shared code:
- `framework/conformance/rule-ids.yaml` enumerates stable, fine-grained rule IDs
  (`LEDGER.EVIDENCE_REQUIRED`, `LEDGER.LEASE_OVERLAP`,
  `CHAIN.UPSTREAM_UNRECONCILED`, `AUDIT.IDENTITY_MISMATCH`, `HASHCHAIN.BROKEN`,
  `ISOLATION.PATH_OUTSIDE_ROOTS`, `MON.SLO_MISSING_TARGET`, …) under the coarse
  categories `IPLAN-007/008/009`, `MON-001` (D-0009).
- `framework/conformance/vectors/<kind>/*.yaml` are input documents; each has a
  sibling `*.expect.yaml` = `{status, rule_ids:[…]}`. Severity is **not** in the
  expectation — it is a fixed property of each rule in the catalog, so
  conformance instead asserts every emitted finding's severity equals the
  catalog's severity for that rule ID.
- Every engine exposes a uniform `validate(document) -> {status,
  findings:[{rule_id, severity, message}]}` (part of the engine-adapter
  contract). Conformance replays each vector through each engine and asserts the
  **rule-ID set + status** match the expectation (and each finding's severity
  matches the catalog); human message text is **not** compared (it will
  legitimately differ between independent implementations).
- Coverage is enforced both ways: every catalog rule has ≥1 vector, and every
  emitted/expected rule ID is in the catalog.
- Ground truth is in the spec, so a future engine (`codex`, `vertexai`) can be
  certified against the vectors **alone**. Once ≥2 engines exist, a
  **cross-engine differential** test additionally asserts the engines agree with
  *each other* on every vector (defense-in-depth on top of the golden answers).

**Validators emit findings, not strings.** Re-homing the attached plan's
validator logic, each finding becomes `{rule_id, severity, message}` (the
attached plan appended plain strings under coarse codes). The coarse code is
derived from the rule ID's category. Validators stay deterministic, pure, no I/O.

**OpenTelemetry is an optional extra per engine (R5).** Each engine defines a
small `MonitoringProvider` interface with a console/no-op default; the OTLP/OTel
SDK lives behind that engine's `[otel]` extra. Absent it (offline container),
the no-op provider is used; SLO evaluation operates on supplied samples and is
exporter-independent. All tests + conformance run with only `pyyaml`.

**Source-IPLAN binding is real.** Each engine's `iplan.read_iplan_ref(path)`
reads any SDD IPLAN-shaped YAML (read-only) → `{id, version, last_updated,
checksum}` where `checksum = "sha256:" + sha256(file_bytes)`. Populates a
ledger's `ledger_control.source_iplan*` without depending on the SDD repo.

**Dev setup.** `src/` layout per engine, installed editable for tests/types:
`pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"`.
Conformance itself needs only `pyyaml` and imports the engines (test code may
import engines; engines must not import each other).

**Test-first where logic is non-trivial.** Per engine, the ledger store,
validators, hash-chain, and gate runner are built TDD-style against the
re-homed cases; the golden vectors are authored in `framework/` first so both
engines are implemented to the same target.

## File Structure

| Path | Responsibility |
|------|----------------|
| `CLAUDE.md` | Repo dev workflow + durable conventions (adapted from SDD; strict isolation rule). |
| `README.md` | What the framework is; control-plane vs execution-plane relationship to SDD. |
| `CHANGELOG.md` | Keep-a-changelog; `[Unreleased]`; tracks repo releases. |
| `.gitignore` | Python + tooling ignores. |
| `framework/VERSION` | **Single** spec-version source (`0.1.0`); registry + every engine must match. |
| `framework/README.md` | IPLAN / Ledger / Gate / Monitor model overview. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | Single source of truth: artifacts, engines, coarse codes, rule-ID catalog ref. |
| `framework/execution/IPLAN-LEDGER-TEMPLATE.yaml` | Ledger: task state, leases, evidence, blockers, reconciliation, saga journal, execution history, hash-chained execution log, audit snapshots. |
| `framework/execution/IPLAN-VERIFY-TEMPLATE.yaml` | Verification-gate rules (GATE-LEDGER-001..005) + outcomes. |
| `framework/execution/IPLAN-CHAIN-LEDGER-TEMPLATE.yaml` | Ordered multi-IPLAN execution path + chain reconciliation. |
| `framework/execution/IPLAN-AUDIT-REPORT-TEMPLATE.yaml` | Execution history + version-comparison report. |
| `framework/execution/AGENT_UPDATE_PROTOCOL.md` | Mandatory agent update protocol. |
| `framework/execution/HOOK_INTEGRATION_POINTS.md` | Platform hook guardrails + authority limits. |
| `framework/execution/SAGA_EXECUTION_MODEL.md` | Saga-lite transactions, retries, compensation, escalation, journaling. |
| `framework/execution/LEDGER_ISOLATION_MODEL.md` | Task/project/client isolation boundaries. |
| `framework/execution/README.md` | Ledger semantics, status model, lease/evidence/reconciliation rules. |
| `framework/monitoring/MONITORING-MANIFEST-TEMPLATE.yaml` | OTel-aligned SLOs, signals, probes, alerts, bound to `@iplan` + `@ledger`. |
| `framework/monitoring/POST_IMPLEMENTATION_MONITORING.md` | Monitoring model, OTel mapping, SLO evaluation, window. |
| `framework/monitoring/README.md` | Monitoring contract overview. |
| `framework/engines/ENGINE-ADAPTER-CONTRACT.md` | Interface every engine implements, incl. `validate(document)` parity entry point + capabilities. |
| `framework/conformance/rule-ids.yaml` | Canonical fine-grained rule-ID catalog (id, category, severity, description). |
| `framework/conformance/RULE-IDS.md` | Human-readable rule catalog. |
| `framework/conformance/vectors/<kind>/*.yaml` | Golden input docs (kind ∈ ledger/chain/audit/monitoring). |
| `framework/conformance/vectors/<kind>/*.expect.yaml` | Expected `{status, rule_ids}` per input (severity checked against the catalog). |
| `platforms/<engine>/pyproject.toml` | Standalone package (`iops_<engine>`); base dep `pyyaml`; `[otel]` + `[dev]` extras; console script `iops-<engine>`. |
| `platforms/<engine>/VERSION`, `platforms/<engine>/FRAMEWORK_SPEC_VERSION` | Engine version + spec parity. |
| `platforms/<engine>/README.md` | Engine-specific expectations. |
| `platforms/<engine>/src/iops_<engine>/iplan.py` | Read-only SDD IPLAN reference reader. |
| `platforms/<engine>/src/iops_<engine>/ledger/store.py` | Append-only ledger load/append; hash-chain. |
| `platforms/<engine>/src/iops_<engine>/ledger/isolation.py` | Isolation-scope + touched-path ⊆ `allowed_roots`. |
| `platforms/<engine>/src/iops_<engine>/validation/{ledger,chain,audit,monitoring}_rules.py` | Validators emitting `{rule_id, severity, message}`. |
| `platforms/<engine>/src/iops_<engine>/gates/runner.py` | Verify-gate runner (maps GATE-LEDGER-NNN ↔ rule IDs). |
| `platforms/<engine>/src/iops_<engine>/audit/report.py` | Audit + version-comparison generation. |
| `platforms/<engine>/src/iops_<engine>/monitoring/{provider,otel,slo}.py` | Monitoring provider (no-op default), optional OTel, SLO eval. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | Adapter implementing the engine-adapter contract incl. `validate(document)`. |
| `platforms/<engine>/src/iops_<engine>/cli.py` | `iops-<engine>` entry point; `main(argv)->int`. |
| `platforms/<engine>/src/iops_<engine>/py.typed` | Typing marker for `mypy --strict`. |
| `platforms/<engine>/tests/` | Per-engine unit + integration tests. |
| `tests/conformance/_spec.py` | Locate `framework/`, load registry + rule catalog + discover vectors + engines. |
| `tests/conformance/test_contract.py` | Templates parse + metadata matches registry; protocol docs present. |
| `tests/conformance/test_registry.py` | Registry integrity; `spec_version == framework/VERSION`. |
| `tests/conformance/test_rule_catalog.py` | Catalog well-formed; every catalog rule has ≥1 vector; every vector rule is in the catalog. |
| `tests/conformance/test_vectors.py` | Replay each vector through each engine's `validate`; assert status + rule-ID set match `*.expect.yaml`. |
| `tests/conformance/test_engines.py` | Strict isolation (no cross-engine imports); `FRAMEWORK_SPEC_VERSION == framework/VERSION`. |
| `tests/conformance/test_differential.py` | Cross-engine agreement: all engines return identical status + rule-ID set per vector. |
| `tests/conformance/requirements.txt` | `pyyaml`. |

## Step Sequence

### Task 1: Repo conventions & scaffolding

**Files:** Create `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `.gitignore`,
`framework/VERSION`, `framework/README.md`.

- [ ] **Step 1: `CLAUDE.md`** — project purpose (execution/ops plane, D-0002);
  plan → ≥2-review → implement → verify → land workflow; durable conventions
  (spec is the contract; **strict isolation** — engines import only the spec,
  never each other, D-0011; parity is proven by golden vectors, D-0012;
  conformance stays green; single source of truth = registry); handoff via
  `plans/HANDOFF.md` ("only committed + pushed work survives").
- [ ] **Step 2: `README.md`** — model, relationship to SDD, repo map.
- [ ] **Step 3: `framework/VERSION` (`0.1.0`); `CHANGELOG.md` (Keep-a-Changelog,
  `[Unreleased]`); `.gitignore`** (`.venv`, `__pycache__`, `*.egg-info`,
  `.pytest_cache`, `.mypy_cache`).
- [ ] **Step 4: `framework/README.md`** — model framing + links.
- [ ] **Step 5: Commit** — `git commit -m "chore: scaffold repo conventions"`.

### Task 2: Engine-agnostic execution contract

**Files:** Create the four `framework/execution/*.yaml` templates, four
`*.md` protocol docs, and `framework/execution/README.md`.

- [ ] **Step 1: `IPLAN-LEDGER-TEMPLATE.yaml`** — re-home from the attached plan
  (Task 1 Step 1); `document_type: "iplan-ledger"`, `framework: iops`, drop
  `layer: 8`. Keep `ledger_control` (with `source_iplan*`), `isolation_scope`,
  `task_ledger`, `agent_leases`, `execution_evidence`, `blockers`,
  `reconciliation`, `saga_journal`, `execution_history`, `execution_log`
  (hash-chained), `audit_snapshots`.
- [ ] **Step 2: `IPLAN-CHAIN-LEDGER-TEMPLATE.yaml`** — re-home (attached Task 1
  Step 2): `chain_control`, `iplan_chain`, `execution_tiers`, `cross_plan_leases`,
  `chain_gate_results`, `chain_reconciliation`.
- [ ] **Step 3: `IPLAN-AUDIT-REPORT-TEMPLATE.yaml`** — re-home (attached Task 1
  Step 3): `audit_control`, `version_scope`, `execution_summary`, `change_report`,
  `audit_findings`, `recommendation`.
- [ ] **Step 4: `IPLAN-VERIFY-TEMPLATE.yaml`** — re-home (attached Task 1 Step 4):
  `gate_control`, `gate_rules` (GATE-LEDGER-001..005), `gate_results`.
- [ ] **Step 5: Protocol docs** — re-home `AGENT_UPDATE_PROTOCOL.md`,
  `HOOK_INTEGRATION_POINTS.md`, `SAGA_EXECUTION_MODEL.md`,
  `LEDGER_ISOLATION_MODEL.md` (attached Task 3); re-point links to
  `framework/execution/`.
- [ ] **Step 6: `framework/execution/README.md`** — ledger semantics, status
  model, lease/evidence/reconciliation rules (attached Task 4 Steps 1–2).
- [ ] **Step 7: Parse check** — `python -c "import glob,yaml;[yaml.safe_load(open(f)) for f in glob.glob('framework/execution/*.yaml')]"`.
- [ ] **Step 8: Commit** — `git commit -m "feat: add engine-agnostic execution ledger contract"`.

### Task 3: Monitoring contract

**Files:** Create `framework/monitoring/MONITORING-MANIFEST-TEMPLATE.yaml`,
`POST_IMPLEMENTATION_MONITORING.md`, `README.md`.

- [ ] **Step 1: `MONITORING-MANIFEST-TEMPLATE.yaml`** — `metadata`
  (`document_type: "iplan-monitoring-manifest"`, `framework: iops`),
  `monitor_control` (`source_iplan`, `source_ledger`, `monitoring_window`),
  `slos` (id/objective/unit/window/signal_ref), `signals.otel`
  (traces/metrics/logs with attributes `iplan.id`/`ledger.id`/`task.id`/
  `client.id`/`project.id`), `probes` (health/readiness/startup), `alert_rules`.
- [ ] **Step 2: `POST_IMPLEMENTATION_MONITORING.md`** — monitoring binds to the
  same `@iplan`/`@ledger` identity; OTel signal mapping; SLO evaluation; window;
  alert escalation (future observability-driven issue loop). Cite D-0006.
- [ ] **Step 3: `framework/monitoring/README.md`**.
- [ ] **Step 4: Parse check + Commit** — `git commit -m "feat: add otel post-implementation monitoring contract"`.

### Task 4: Engine-adapter contract, registry, rule-ID catalog

**Files:** Create `framework/engines/ENGINE-ADAPTER-CONTRACT.md`,
`framework/registry/EXECUTION_REGISTRY.yaml`,
`framework/conformance/rule-ids.yaml`, `framework/conformance/RULE-IDS.md`.

- [ ] **Step 1: `ENGINE-ADAPTER-CONTRACT.md`** — define the interface each engine
  implements: `engine_id()`, `capabilities()`, **`validate(document) ->
  {status, findings:[{rule_id, severity, message}]}`** (the parity entry point;
  dispatch by `metadata.document_type`), `run_gate(ledger, gate)`,
  `record_transaction(ledger, txn)`, `emit_execution_log(event)`,
  `instrument(manifest)`. State the strict-isolation rule (D-0011) and that
  `validate` outcomes are compared by rule-ID set + status only (D-0012).
- [ ] **Step 2: `rule-ids.yaml`** — canonical catalog; each entry `{id, category,
  severity, description}`. Enumerate ledger/chain/audit/monitoring/hashchain/
  isolation rules covering every failure condition in the attached plan's
  validators (e.g. `LEDGER.EVIDENCE_REQUIRED` → category `IPLAN-007`, severity
  `error`). `RULE-IDS.md` documents them in a table.
- [ ] **Step 3: `EXECUTION_REGISTRY.yaml`** — `metadata.spec_version: "0.1.0"`;
  `artifacts[]` (ledger/verify/chain/audit/monitoring → template path +
  document_type + coarse error_prefix); `protocol_docs[]`; `rule_catalog:
  "framework/conformance/rule-ids.yaml"`; `vectors_root:
  "framework/conformance/vectors"`; `engines[]` (`hermes`→`iops_hermes`,
  `claude`→`iops_claude`, with `path`).
- [ ] **Step 4: Parse check + Commit** — `git commit -m "feat: add engine-adapter contract, registry, and rule-id catalog"`.

### Task 5: Golden conformance vectors

**Files:** Create `framework/conformance/vectors/{ledger,chain,audit,monitoring}/*.yaml`
+ sibling `*.expect.yaml`.

- [ ] **Step 1: Author valid baselines** — one passing document per kind
  (`status: pass`, `rule_ids: []`), derived from the templates with realistic
  values (timestamps, a real-looking `sha256:` checksum, reconciled state).
- [ ] **Step 2: Author invalid cases** — one vector per catalog rule, lifted from
  the attached plan's Task 5 test cases (missing evidence, weak acceptance,
  blocked-without-owner, overlapping leases, unreconciled-but-allowed,
  missing source-version metadata, out-of-scope isolation, event isolation
  breach, touched-path-outside-roots, broken hash-chain, chain out-of-order,
  upstream-unreconciled, cross-plan lease overlap, audit identity/version
  mismatch, monitoring SLO missing target). Each `*.expect.yaml` lists the exact
  `rule_ids` set + `status: fail`.
- [ ] **Step 3: Self-check** — a small throwaway script asserts every vector
  parses and every `expect` rule ID exists in `rule-ids.yaml` (the real coverage
  test lands in Task 8).
- [ ] **Step 4: Commit** — `git commit -m "test: add golden conformance vectors"`.

### Task 6: Hermes engine (full, self-contained, TDD)

**Files:** `platforms/hermes/{pyproject.toml,VERSION,FRAMEWORK_SPEC_VERSION,README.md}`,
`platforms/hermes/src/iops_hermes/**`, `platforms/hermes/tests/**`.

- [ ] **Step 1: Package files** — `pyproject.toml` (`iops_hermes`, Python ≥3.11,
  base dep `pyyaml`; `[otel]` = opentelemetry-{api,sdk}, otlp exporter; `[dev]` =
  pytest/ruff/mypy; console script `iops-hermes = iops_hermes.cli:main`);
  `VERSION` (`0.1.0`); `FRAMEWORK_SPEC_VERSION` (`0.1.0`); `py.typed`.
- [ ] **Step 2: Failing unit tests** — re-home the attached plan's Task 5 cases as
  standalone-document tests against `validation/*` (asserting emitted
  **rule IDs**), plus hash-chain (`HASHCHAIN.BROKEN`), isolation
  (`ISOLATION.PATH_OUTSIDE_ROOTS`), monitoring (`MON.*`). Run `pytest
  platforms/hermes -q` → failures.
- [ ] **Step 3: `iplan.py`** — `read_iplan_ref(path)` → `{id, version,
  last_updated, checksum="sha256:"+sha256(bytes)}`, tolerant of missing fields.
- [ ] **Step 4: `ledger/store.py`** — `load_ledger`, `append_event` (`event_hash
  = sha256(f"{sequence}|{previous_event_hash}|{event_type}|{subject_id}|{at}")`),
  `verify_chain`; append-only (never mutate prior events).
- [ ] **Step 5: `ledger/isolation.py`** — `in_scope(path, allowed_roots)`,
  `assert_event_isolation(event)`.
- [ ] **Step 6: `validation/{ledger,chain,audit,monitoring}_rules.py`** — re-home
  the attached plan's validator logic, but emit `{rule_id, severity, message}`
  findings keyed to `rule-ids.yaml` (coarse code derived from category).
- [ ] **Step 7: `gates/runner.py`** — evaluate a verify-gate doc against a ledger,
  mapping each `GATE-LEDGER-NNN` to the relevant rule IDs; per-rule + overall status.
- [ ] **Step 8: `audit/report.py`** — build + validate an audit report from
  baseline + comparison ledgers.
- [ ] **Step 9: `monitoring/{provider,otel,slo}.py`** — `MonitoringProvider`
  (console/no-op default), lazy OTel-backed provider behind `[otel]`,
  `evaluate_slos(manifest, samples)` (samples as dict/JSON).
- [ ] **Step 10: `engine.py`** — `HermesEngine` implementing the adapter incl.
  `validate(document)` (dispatch by `document_type` to the validators, aggregate
  to `{status, findings}`); MCP-style tool fns (`iops_validate_ledger`,
  `iops_run_gate`, `iops_audit_report`, `iops_monitor_check`); `run_executor`
  stub wrapped with execution-log emission; `instrument` sets OTel
  `service.name="iops-hermes"`. **No import of `iops_claude`.**
- [ ] **Step 11: `cli.py`** — `main(argv)->int`: `ledger validate|show|append`,
  `gate run`, `audit report`, `monitor validate|slo-check`.
- [ ] **Step 12: Integration test** — read IPLAN ref → build ledger → append
  hash-chained events → `verify_chain` → run gate → 2-plan chain reconcile →
  audit report. Run `pytest platforms/hermes -q`, `ruff check platforms/hermes`,
  `mypy --strict platforms/hermes/src` → green.
- [ ] **Step 13: `README.md`** — Hermes expectations (attached Task 6 Step 2).
- [ ] **Step 14: Commit** — `git commit -m "feat: add self-contained hermes execution engine"`.

### Task 7: Claude engine (full, self-contained, TDD)

**Files:** `platforms/claude/{pyproject.toml,VERSION,FRAMEWORK_SPEC_VERSION,README.md}`,
`platforms/claude/src/iops_claude/**`, `platforms/claude/tests/**`.

- [ ] **Step 1–9: Re-implement the full runtime independently** — its **own**
  copies of `iplan.py`, `ledger/`, `validation/`, `gates/`, `audit/`,
  `monitoring/` (same contract, emitting the same rule IDs), with its own
  failing-first unit tests. Package files mirror Task 6 Step 1 but for
  `iops_claude` / console script `iops-claude`. **No import of `iops_hermes`.**
- [ ] **Step 10: `engine.py`** — `ClaudeEngine` implementing the adapter incl.
  `validate(document)`; plus `AGENT_UPDATE_PROTOCOL` methods (`start_session`,
  `acquire_lease`, `record_touched_file`, `record_evidence`, `reconcile`)
  recording ledger transactions via its own `ledger.store`; `instrument` sets
  `service.name="iops-claude"`. Slice 1 exercises these programmatically; live
  Claude Code hook wiring is a follow-up (documented in README).
- [ ] **Step 11: `cli.py`** — `iops-claude` `main(argv)->int` (same commands).
- [ ] **Step 12: Integration test** — same lifecycle as Task 6 Step 12. Run
  `pytest platforms/claude -q`, `ruff`, `mypy --strict platforms/claude/src` → green.
- [ ] **Step 13: `README.md`** — Claude hook-guardrail expectations (attached
  Task 6 Step 1).
- [ ] **Step 14: Commit** — `git commit -m "feat: add self-contained claude execution engine"`.

### Task 8: Conformance suite

**Files:** `tests/conformance/{_spec.py,test_contract.py,test_registry.py,
test_rule_catalog.py,test_vectors.py,test_engines.py,test_differential.py,requirements.txt}`.

- [ ] **Step 1: `_spec.py`** — locate `framework/`, load registry, rule catalog,
  discover `(input, expect)` vector pairs, and attempt to import each engine's
  adapter. Engines that are not importable are recorded as skipped (so the
  contract/registry/catalog tests still run with only `pyyaml`); vector +
  differential tests run for the engines that import.
- [ ] **Step 2: `test_contract.py`** — every `artifacts[].template` parses + its
  `metadata.document_type` matches the registry; every `protocol_docs[]` exists.
- [ ] **Step 3: `test_registry.py`** — registry parses; ids/error_prefixes unique;
  paths exist; `spec_version == framework/VERSION`.
- [ ] **Step 4: `test_rule_catalog.py`** — catalog well-formed (unique ids, valid
  categories/severities); **every catalog rule appears in ≥1 vector**; **every
  rule ID used in any `*.expect.yaml` is in the catalog**.
- [ ] **Step 5: `test_vectors.py`** — parametrized over (importable engine ×
  vector): call `engine.validate(input)`; assert `status` and the **set** of
  `rule_id`s equal the `*.expect.yaml`, and each finding's `severity` equals the
  catalog severity for its rule ID (message text ignored). Skips if no engine
  imports.
- [ ] **Step 6: `test_engines.py`** — each `engines[].path` exists;
  `FRAMEWORK_SPEC_VERSION == framework/VERSION`; **strict isolation** — grep each
  engine's `src/` for any reference to another engine's package name
  (`iops_<other>`) and assert none.
- [ ] **Step 7: `test_differential.py`** — for every vector, all importable
  engines return the identical `{status, rule_id set}` (defense-in-depth,
  D-0012). Skips when fewer than two engines import.
- [ ] **Step 8: Run** `python -m unittest discover -s tests/conformance -v` (with
  both engines installed) → all pass. **Commit** — `git commit -m "test: add vector-replay + isolation conformance suite"`.

### Task 9: Changelog, handoff, decisions finalize

- [ ] **Step 1:** `CHANGELOG.md` `[Unreleased] → Added`: contract + rule catalog
  + vectors, hermes + claude engines, OTel monitoring, conformance.
- [ ] **Step 2:** Update `plans/HANDOFF.md` (branch, done tasks, next engines).
- [ ] **Step 3:** Set PLAN-001 `Status: DONE - <ISO>`.
- [ ] **Step 4: Full verification** (below). **Commit** — `git commit -m "docs: record iops execution framework slice 1"`.

## Verification

> Nothing is "done" until these pass. Run from repo root.

```bash
# one-time dev setup (editable installs; [otel] optional)
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"

python -m unittest discover -s tests/conformance -v    # vectors + isolation + parity
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
git status --short --branch
```

Expected:

1. Conformance passes: contract parses + matches registry; rule catalog fully
   covered; **every vector yields the expected status + rule-ID set in each
   engine**; engines agree with each other; no cross-engine imports; spec parity.
2. Per-engine unit + integration tests pass (validators reject the attached
   plan's invalid cases with the right rule IDs; hash-chain links; gate + audit +
   monitoring behave).
3. Lint + strict types clean.
4. Two independent engines produce identical verdicts from shared vectors.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Re-homing drifts from the attached plan's validated rules. | Re-home logic + cases verbatim; the only change is emitting `{rule_id,…}` findings; vectors pin the result. |
| R2 | Contract leaks engine specifics. | `framework/` stays code-free; engines import only the spec; conformance forbids cross-engine imports. |
| R3 | Duplicated logic across engines diverges silently. | Golden vectors (D-0012) + cross-engine differential test make divergence a test failure. |
| R4 | Vector corpus under-covers a rule, allowing drift there. | `test_rule_catalog` requires every catalog rule to have ≥1 vector; corpus seeded from the attached plan's full case list. |
| R5 | OTel deps heavy / unavailable offline. | Per-engine optional `[otel]` extra behind a `MonitoringProvider`; no-op default; SLO eval + tests run with only `pyyaml`. |
| R6 | Python 3.11 vs SDD's 3.12. | Target 3.11 builtin generics only; no 3.12-only syntax (D-0010). |
| R7 | Ledger treated as self-attested. | Completed tasks require evidence + acceptance; the gate is the authority. |
| R8 | Append-only claim unauditable. | `sequence`/`previous_event_hash`/`event_hash` validated; `verify_chain` tested; `HASHCHAIN.BROKEN` vector. |
| R9 | Cross-project/client leakage. | Isolation scope + touched-path ⊆ `allowed_roots`; `ISOLATION.*` vectors. |
| R10 | `claude` CLI clashes with Claude Code CLI. | Console script `iops-claude`, package `iops_claude`. |
| R11 | A vector's *expected* answer is itself wrong → both engines "agree" on a bug. | Golden expectations derive from the documented rules and are reviewed; differential test is a secondary, not primary, guard. |
| R12 | Rule-ID catalog and validators drift apart. | `test_rule_catalog` cross-checks catalog ↔ vectors ↔ emitted IDs both directions. |
| R13 | Two full engines = large slice. | Tasks are independently committable; engines built sequentially against the same pre-authored vectors. |
| R14 | Conformance can't run without engine installs. | Structural/contract/catalog tests need only `pyyaml`; vector-replay + differential require the editable installs in Verification. |

## Review log

> At least two passes before implementation. Each pass: re-read the whole plan,
> list findings, fold fixes back into the sections above. Stop when a pass finds
> nothing.

### Pass 1 - 2026-05-23 (pre-rework, shared-core design)

- Added real source-IPLAN binding (`read_iplan_ref` + sha256), test fixtures,
  OTel-as-optional-extra behind a provider interface, editable-install dev setup,
  registry spec-version parity, concrete per-engine `instrument()`, and extended
  the integration test to chain + audit. (Applied to the prior shared-core draft.)

### Pass 2 - 2026-05-23 (pre-rework, shared-core design)

- Removed the root `VERSION` drift trap (single source = `framework/VERSION`);
  specified the gate-rule ↔ validator mapping; clarified `claude` is exercised
  programmatically in slice 1; added `py.typed`; cross-checked Verification ↔
  rules. No further findings against that design.

### Pass 3 - 2026-05-23 (post-rework: strict isolation + golden vectors)

- Reworked the entire plan for D-0011 (strict isolation, no shared `core/`) and
  D-0012 (golden vectors + fine-grained rule IDs). Findings folded in during the
  rewrite:
  - The attached plan's validators append plain strings under coarse codes,
    which is too imprecise for parity. Change: validators now emit
    `{rule_id, severity, message}`; added `framework/conformance/rule-ids.yaml`
    + `RULE-IDS.md`; comparison is on rule-ID **set** + status, ignoring messages.
  - Parity needs ground truth, not just engine-vs-engine. Change: golden
    `*.expect.yaml` per vector (engine-vs-spec) is primary; `test_differential`
    (engine-vs-engine) is secondary (R11).
  - Coverage could silently lapse. Change: `test_rule_catalog` enforces
    catalog↔vector bidirectional coverage (R4, R12).
  - Conformance now imports engines (to call `validate`); confirmed this does not
    violate isolation (test code may import engines; engines must not import each
    other) and recorded the install requirement (R14).
  - Removed every reference to `core/`/`iops_core`; duplicated the full runtime
    into each `platforms/<engine>/src/`; verification installs both engines.

### Pass 4 - 2026-05-23 (post-rework re-read)

- Finding: `*.expect.yaml` schema was inconsistent — described as `{status,
  rule_ids, severities}` in some places and `{status, rule_ids}` in others.
  Change: expectation is `{status, rule_ids}`; severity is a fixed catalog
  property, and `test_vectors` instead asserts each emitted finding's severity
  equals the catalog severity for its rule ID. Aligned Approach, file structure,
  Task 8 Step 5, and D-0012.
- Finding: conformance imports engines to call `validate`, but the
  contract/registry/catalog tests should still run with only `pyyaml` (and the
  differential test is meaningless with <2 engines). Change: `_spec.py` records
  non-importable engines as skipped; `test_vectors` runs over importable engines
  only; `test_differential` skips when <2 engines import. Verification still
  installs both, so the full matrix runs there.
- Finding: "every emitted rule is in the catalog" is enforced only indirectly.
  Confirmed acceptable: a typo'd/unknown rule ID makes the engine's rule-ID set
  diverge from `*.expect.yaml`, failing `test_vectors`; `test_rule_catalog`
  covers catalog↔vector directly. No extra check needed.
- No further structural findings; the plan is internally consistent and ready
  for approval.
