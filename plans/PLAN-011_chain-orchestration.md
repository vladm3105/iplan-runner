# Chain Orchestration Runtime Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** Execute multi-IPLAN **chains** (Roadmap Phase 11 → `v0.11.0`). Today the
chain-ledger contract is only *validated* (`CHAIN.*`); PLAN-011 adds the runtime
that **drives** a chain — runs each IPLAN in dependency/tier order, gates each on
its upstream being reconciled, coordinates cross-plan leases, and produces a
reconciled **chain ledger**. It composes the single-IPLAN run loop (PLAN-003).

**Architecture:** Additive (D-0014). New `framework/execution/CHAIN_MODEL.md` + a
`chains/` conformance kind. Two regimes: the **chain order** (pure topo) and the
**chain execution** (composing per-IPLAN runs with injected clock/ids) are pinned
by chain scenarios + cross-engine differential (D-0012); the per-IPLAN run loop
is unchanged. Engines stay isolated (D-0011); chain runtime is copied identically
(engine-agnostic orchestration over the shared loop).

**Tech Stack:** Python ≥3.11; `pytest`; `unittest` conformance; `ruff` +
`mypy --strict`; YAML.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-011 |
| Depends on | `PLAN-001`..`PLAN-010` (DONE); D-0011..D-0015; Roadmap Phase 11 |
| Status     | DONE - 2026-05-24 |
| Feeds      | GA (`v1.0.0`); multi-tenant control plane (post-v1.0) |

## Objective

An IPLAN rarely ships alone. PLAN-011 executes a **chain** of IPLANs:

1. **Chain order.** `chain_order(iplan_chain) -> [iplan_id]` — a stable
   topological order over `depends_on` (tie-broken by `(order, iplan_id)`),
   tier-consistent.
2. **Upstream gating.** An IPLAN runs only when **all** its `depends_on`
   upstreams reconciled; otherwise it is left unreconciled (chain-level block).
3. **Cross-plan leases.** Per-IPLAN resource leases are coordinated (sequential
   execution → no contention; declared overlaps are caught by `CHAIN.LEASE_OVERLAP`).
4. **Chain reconciliation.** A chain ledger records each node's `reconciled`
   flag; `chain_reconciliation.allowed` iff **every** IPLAN reconciled.

`run_chain` **composes** the PLAN-003 `run` per IPLAN (one injected clock/ids
across the chain → deterministic), so a chain is a meta-run over single-IPLAN
runs — no change to the inner loop.

## Scope

**In:**

1. `framework/execution/CHAIN_MODEL.md` — chain execution order, upstream-reconciled
   gating, cross-plan lease coordination, chain reconciliation, the chain-ledger
   output, and the between-IPLAN control checkpoint. Registry → doc + `chains_root`.
2. Chain scenarios: `framework/conformance/chains/<name>/{scenario,expect}.yaml`
   (chain spec + per-IPLAN intake manifests + per-IPLAN mock outcomes → chain
   projection).
3. Engine-agnostic (copied identically): `orchestrator/chain.py`
   (`chain_order`, `run_chain`, `build_chain_ledger`, `ChainResult`).
4. Per engine: engine `run_chain(...)`; CLI `run-chain <chain-file>`; tests.
5. Conformance: `tests/conformance/test_chains.py` (per-engine chain projection +
   cross-engine differential on the chain ledger); registry path check.
6. Spec bump to `0.11.0`.

**Out:**

1. **Distributed / concurrent** chain execution — single-process, sequential;
   cross-process lease coordination is post-v1.0.
2. **Live executors for chains** — chains run with mock/scripted executors here
   (scenarios); live executors (Phase 8) plug in unchanged via `executor_for`.
3. Embedding full sub-ledgers in the chain ledger — the chain ledger references
   IPLANs by id + records reconciled flags; sub-ledgers are returned separately
   (keeps the chain ledger engine-identity-free for the differential).
4. Changing the single-IPLAN run loop.

## Approach

**Compose, don't reinvent.** `run_chain(chain, iplans, executor_for, *, clock,
ids, sleep, control)` computes `chain_order`, then for each IPLAN: checkpoints
`control` (between IPLANs), verifies upstreams reconciled, and calls the existing
`run(manifest, executor_for(iplan_id), clock=…, ids=…, sleep=…)`. One injected
`clock`/`ids` threads the whole chain, so sub-ledgers + the chain ledger are
deterministic; both engines (copies) produce identical results → differential.

**Upstream gating.** An IPLAN whose `depends_on` aren't all reconciled is **not
run** — its node `reconciled` stays false and the chain can't reconcile. This
mirrors the single-IPLAN dependency-unmet blocking, one level up.

**Cross-plan leases.** Declared `cross_plan_leases` are carried into the chain
ledger; sequential execution means a resource is free by the time the next IPLAN
runs (no contention). Overlapping *unreleased* declarations are a validation
error (`CHAIN.LEASE_OVERLAP`, PLAN-001) — the runtime doesn't create them.

**Chain ledger is identity-free.** `build_chain_ledger` records `iplan_chain`
(with `reconciled`), `execution_tiers`, `cross_plan_leases`, and
`chain_reconciliation` — **not** the sub-ledgers (which carry per-engine
`agent_id`). So the chain-ledger differential needs no normalization; sub-ledgers
are returned in `ChainResult` for inspection. The produced chain ledger validates
against the `CHAIN.*` rules.

**Projection (parity).** A chain scenario's `expect` is `{order, iplan_chain:
{id: {reconciled}}, chain_reconciliation, chain_status}`. Conformance asserts each
engine's projection equals `expect` **and** engines produce identical chain
ledgers.

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/execution/CHAIN_MODEL.md` | Chain order, upstream gating, cross-plan leases, chain reconciliation, control checkpoint. |
| `framework/conformance/chains/<name>/scenario.yaml` | Chain spec + per-IPLAN manifests + per-IPLAN mock outcomes. |
| `framework/conformance/chains/<name>/expect.yaml` | Chain projection. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + `CHAIN_MODEL.md`, `chains_root`. |
| `platforms/<engine>/src/iops_<engine>/orchestrator/chain.py` | `chain_order`, `run_chain`, `build_chain_ledger`, `ChainResult`. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | `run_chain(...)`. |
| `platforms/<engine>/src/iops_<engine>/cli/commands.py` | `run-chain <chain-file>`. |
| `platforms/<engine>/tests/test_chain.py` | order, upstream gating, chain reconciliation, control. |
| `tests/conformance/test_chains.py` | per-engine chain projection + differential. |

## Step Sequence

### Task 1: Framework chain model

- [ ] **Step 1:** `CHAIN_MODEL.md` — `chain_order` (stable topo by `(order,
  iplan_id)`), upstream-reconciled gating, cross-plan lease coordination
  (sequential), chain reconciliation, chain-ledger output, between-IPLAN control.
- [ ] **Step 2:** registry — add the doc + `chains_root: framework/conformance/chains`.
- [ ] **Step 3: commit** — `feat: add chain orchestration model`.

### Task 2: Chain scenarios

- [ ] **Step 1:** `chains/linear/scenario.yaml` — IPLAN-002 depends on IPLAN-001;
  both succeed → both reconciled, `chain_reconciliation.allowed: true`,
  `order: [IPLAN-001, IPLAN-002]`. (expect regenerated in Task 3.)
- [ ] **Step 2:** `chains/upstream_blocks/scenario.yaml` — IPLAN-001 blocks (a
  task fails) → IPLAN-002 not reconciled, chain not allowed.
- [ ] **Step 3: commit** — `test: add chain scenario inputs`.

### Task 3: Hermes implementation (TDD)

- [ ] **Step 1: failing tests** — `chain_order` (linear + tie-break);
  `run_chain` linear → both reconciled, chain allowed; upstream-block → downstream
  not run; control aborts the chain between IPLANs. Fail.
- [ ] **Step 2:** `orchestrator/chain.py` — `chain_order`, `build_chain_ledger`,
  `run_chain` (compose `run`; upstream gating; control checkpoint).
- [ ] **Step 3:** `engine.py` — `run_chain(chain, iplans, executor_for, *, clock,
  ids, sleep=None, control=None)` (wraps with `default_gate`).
- [ ] **Step 4:** `cli/commands.py` — `run-chain <chain-file>` (chain spec +
  iplans + per-IPLAN executors via the default/mock executor).
- [ ] **Step 5: (re)generate chain expectations** from the engine.
- [ ] **Step 6: green** — `pytest`, `ruff`, `mypy --strict`. Commit
  `feat: add chain orchestration to hermes`.

### Task 4: Claude implementation (independent)

- [ ] **Step 1–5:** mirror Task 3 as an independent copy. No import of `iops_hermes`.
- [ ] **Step 6: green** + commit `feat: add chain orchestration to claude`.

### Task 5: Conformance

- [ ] **Step 1:** `test_chains.py` — for each chain scenario × engine: build
  `executor_for` from per-IPLAN mock outcomes + a fixed clock/ids; `run_chain`;
  assert the chain projection equals `expect`; assert engines produce identical
  chain ledgers. Extend `test_registry` to `chains_root`.
- [ ] **Step 2: run full suite** + commit `test: add chain conformance`.

### Task 6: Version bump, changelog, handoff

- [ ] **Step 1:** atomic bump to `0.11.0`.
- [ ] **Step 2:** `CHANGELOG.md` `[0.11.0]`; update `HANDOFF.md` + `TODO.md`;
  plan `DONE`.
- [ ] **Step 3: full verification** + commit `chore: release spec v0.11.0
  (chain orchestration)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green: chain scenarios match `expect` per engine + identical chain
   ledgers (differential); a fully-reconciled (linear) chain ledger validates
   clean under `CHAIN.*`, while an upstream-blocked chain correctly reports
   `CHAIN.UPSTREAM_UNRECONCILED` + `chain_reconciliation.allowed: false`; all
   prior checks unchanged at `0.11.0`.
2. Per-engine tests: chain order; linear chain reconciles; upstream-block leaves
   the downstream unreconciled; control aborts between IPLANs.
3. `ruff` + `mypy --strict` clean.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Chain runtime duplicates the run loop. | It **composes** `run` per IPLAN; no inner-loop change; the per-IPLAN behavior is already pinned. |
| R2 | Sub-ledger engine identity breaks the chain differential. | The chain ledger is identity-free (references IPLANs by id + reconciled flags); sub-ledgers are returned separately, not embedded. |
| R3 | Non-determinism across sub-runs. | One injected `clock`/`ids` threads the whole chain; both engines (copies) produce identical chain ledgers (R-pattern from PLAN-003). |
| R4 | Concurrency/cross-process leases expected. | Out of scope: sequential, single-process; `CHAIN.LEASE_OVERLAP` validates declarations; real concurrency is post-v1.0. |
| R5 | A chain's IPLAN manifest fails intake. | `run` validates each manifest (PLAN-002); a failing manifest aborts that IPLAN's run → its node stays unreconciled. |
| R6 | Prior phases affected. | Additive: new `chain.py` + chain scenarios; the single-IPLAN loop, scenarios, and conformance are unchanged. |

## Review log

> ≥2 passes before implementation.

### Pass 1 - 2026-05-24

- Finding: an upstream-blocked chain ledger legitimately *fails* `CHAIN.*`
  validation (`CHAIN.UPSTREAM_UNRECONCILED`) — so "all produced chain ledgers
  pass validation" was wrong. Clarified: the fully-reconciled (linear) chain
  validates clean; a blocked chain *correctly* reports the unreconciled-upstream
  finding + `chain_reconciliation.allowed: false` (the validator describes
  incompleteness, which is the truthful state).
- Finding: chain expects need a working engine. Confirmed the PLAN-005/009
  pattern — Task 2 authors chain *inputs*; Task 3 regenerates expects.
- Finding: `run_chain` should not reinvent gating. Confirmed it composes
  `loop.run` per IPLAN with one injected `clock`/`ids`; `chain.run_chain` takes a
  `gate`, and `engine.run_chain` supplies `default_gate` (R1/R3).

### Pass 2 - 2026-05-24

- Finding: sub-ledger `agent_id` would break the chain differential. Confirmed
  the chain ledger is **identity-free** (IPLAN ids + reconciled flags only);
  sub-ledgers are returned separately in `ChainResult`, not embedded (R2).
- Finding: cross-plan lease contention. Confirmed out of scope — sequential
  single-process execution frees a resource before the next IPLAN;
  `CHAIN.LEASE_OVERLAP` validates declarations; concurrency is post-v1.0 (R4).
- Finding: a chain IPLAN with a bad manifest. Confirmed `run` validates each
  manifest (PLAN-002); a failing manifest aborts that IPLAN's run, leaving its
  node unreconciled (R5).
- Verification ↔ surface cross-check: chain order + execution are chain-scenario
  pinned + differential; the inner loop and all prior conformance are unchanged.
  No further findings.
