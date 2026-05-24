# Config, Secrets & Live Executors Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** Make execution *real* (Roadmap Phase 8 → `v0.8.0`): a **config +
secrets** contract, **resource governance** (token/cost/time budgets), and the
first **live executors** — `hermes` gets an **`ApiExecutor`** (autonomous: a
model proposes the actions), `claude` gets a **`HostRuntimeExecutor`** (governor:
drive a host agent runtime). This is the **A/B divergence point** (D-0013): the
two engines' executors are *intentionally different* and are **not** cross-engine
differential'd.

**Architecture:** Additive (D-0014). New `framework/config/CONFIG_CONTRACT.md` +
`framework/execution/RESOURCE_GOVERNANCE.md` and a `budget/` conformance kind.
**Three regimes:** (1) **parity** — engine-agnostic **budget** decisions are
golden-vector'd + differential; (2) **offline per-engine** — live executors are
built behind a pluggable transport (`ModelClient` / `RuntimeClient`) and tested
against **stubs**, deterministic and network-free; (3) **integration-only** —
real model/host clients are optional extras, **opt-in, keyed, not in CI**. The
run loop and `MockExecutor` scenarios are unchanged (budgets default to
unlimited), so all prior conformance stays green.

**Tech Stack:** Python ≥3.11; optional extras (`anthropic`/`litellm`); `pytest`;
`unittest` conformance; `ruff` + `mypy --strict`; YAML.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-008 |
| Depends on | `PLAN-001`..`PLAN-007` (DONE); D-0011..D-0015; Roadmap Phase 8 |
| Status     | IN REVIEW - 2026-05-24 |
| Feeds      | `PLAN-009` (HITL approves live runs); `PLAN-010` (monitoring of live runs); follow-on engines (`codex`, `vertexai`) |

## Objective

PLAN-004 deferred *action generation* to the live executor; PLAN-008 delivers it,
plus the config/secrets and cost controls a real run needs:

1. **Config + secrets.** A documented config schema (common: timeouts, budgets,
   telemetry endpoint, secret sourcing; per-engine: provider/model, host-runtime
   path) loaded from file + env; no secrets in the repo.
2. **Resource governance.** A `Budget` (max tokens / cost / wall-time) + a pure
   `check(budget, usage) -> {allowed, reason}` the executor consults before/after
   each model call; over budget → the task is blocked (not retried).
3. **`hermes` `ApiExecutor`** (autonomous): build a prompt from the task, call a
   model via a pluggable `ModelClient`, **parse the response into typed actions**
   (output is data, never instructions — SECURITY_MODEL), apply them through the
   PLAN-004 effectors (sandboxed) + evidence runner, report usage to the budget.
4. **`claude` `HostRuntimeExecutor`** (governor): hand the task to a host agent
   runtime via a pluggable `RuntimeClient`, observe the changes it made, and
   record them as an `ExecutorResult`. Real Claude Code hook wiring is documented
   + adapter-stubbed.

## Scope

**In:**

1. `framework/config/CONFIG_CONTRACT.md` — config schema (common + per-engine),
   env/file loading, secret sourcing (extends `secrets_from_env`).
   `framework/execution/RESOURCE_GOVERNANCE.md` — `Budget` shape + `BUDGET.*`
   reason codes (`OK`, `TOKENS_EXCEEDED`, `COST_EXCEEDED`, `TIME_EXCEEDED`).
   Registry → docs + `budget_root`.
2. Golden vectors: `framework/conformance/budget/<name>` (`{budget, usage}` →
   `{allowed, reason}`).
3. Engine-agnostic (copied identically, parity-pinned): `budget.py`
   (`Budget`, `check`); config loader (`load_config`).
4. `hermes` (autonomous): `executor/api.py` (`ApiExecutor`), `model/client.py`
   (`ModelClient` Protocol + `StubModelClient`; real client behind `[anthropic]`
   / `[litellm]` extra), prompt build + action parsing; engine
   `api_executor(...)`.
5. `claude` (governor): `executor/hostruntime.py` (`HostRuntimeExecutor`),
   `runtime/client.py` (`RuntimeClient` Protocol + `StubRuntimeClient`; real
   Claude Code hook adapter documented); engine `host_executor(...)`.
6. Conformance: `tests/conformance/test_budget.py` (cross-engine budget-decision
   parity); registry path check. Live executors are **per-engine stub tests**,
   not conformance.
7. Spec bump to `0.8.0`.

**Out:**

1. **Real network calls in CI** — the real `ModelClient`/`RuntimeClient` are
   optional extras, exercised only by **opt-in, keyed integration tests** (marked
   + skipped without credentials); never in conformance/CI.
2. **Cross-engine differential on the live executors** — they are *intentionally
   different* (A vs B, D-0013); only engine-agnostic policy (budgets) is parity'd.
3. Provider/model lock-in — `ModelClient` is pluggable; real clients are extras.
4. A full Claude Code hook runtime — documented + adapter-stubbed; live wiring is
   environment-specific.
5. Run-loop changes — budgets are enforced *inside* the new executors, so the
   shared loop and `MockExecutor` scenarios are untouched.

## Approach

**The engines diverge here, on purpose.** Both live executors implement the same
`Executor` Protocol (so they plug into the unchanged run loop), but `hermes`'s
`ApiExecutor` (a model generates actions) and `claude`'s `HostRuntimeExecutor` (a
host runtime does the work) are different designs — the D-0013 A/B choice, made
per engine. They are **not** copied between engines and **not** differential'd.
What stays parity-pinned is the engine-agnostic **budget** policy (copied
identically, vector'd) and the contract.

**Offline by construction.** Each live executor talks to a **pluggable
transport** — `ModelClient` (hermes) / `RuntimeClient` (claude) — with a
deterministic **stub** implementation. Unit tests drive the executor end-to-end
through the stub (canned model response / canned runtime result → parsed actions
→ sandboxed apply → evidence), entirely offline. The **real** clients
(`anthropic`/`litellm`, Claude Code) live behind extras and are only used by
integration tests gated on credentials (skipped otherwise).

**Untrusted output (SECURITY_MODEL).** The `ApiExecutor` treats the model
response as **data**: it parses it into the **same typed action/check schema**
the `ScriptedExecutor` uses (PLAN-004) and applies those through the shared
PLAN-004 sandbox + evidence runner. Model text is never executed as instructions;
a malformed/over-scope action is denied by the sandbox, blocking the task. (So
the model is just the *action generator* PLAN-004 deferred.)

**Real clients are import-guarded.** `AnthropicClient`/`LiteLLMClient` and the
real Claude Code adapter are imported lazily (importlib, like the OTel provider),
so the base package builds and `mypy --strict` passes with only `pyyaml`;
absence degrades to the stub.

**Budget is per-executor-instance.** The executor is constructed with a `Budget`
and tracks cumulative usage across the tasks of one run (the run loop reuses one
executor instance), checking `check(budget, total)` before each model call.

**Budgets are pure → vector'd; default unlimited.** `Budget` fields default to
`None` (unlimited), so a default run enforces nothing and every prior scenario is
unchanged. `check(budget, usage)` is a deterministic decision over accumulated
usage; the `ApiExecutor` consults it before each model call and on the running
total, returning a `failure` (blocked, non-retriable) when exceeded.

**Config + secrets.** `load_config(path, env)` merges a YAML file + env overrides
into the engine `Config`; secrets come from env (`secrets_from_env`, PLAN-007) —
never the file/repo. The contract documents common keys and the per-engine
executor keys.

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/config/CONFIG_CONTRACT.md` | Config schema (common + per-engine), env/file loading, secret sourcing. |
| `framework/execution/RESOURCE_GOVERNANCE.md` | `Budget` shape + `BUDGET.*` reason codes + enforcement semantics. |
| `framework/conformance/budget/<name>/{input,expect}.yaml` | `{budget, usage}` → `{allowed, reason}`. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + the two docs, `budget_root`. |
| `platforms/<engine>/src/iops_<engine>/budget.py` | `Budget` + `check` (engine-agnostic, identical). |
| `platforms/<engine>/src/iops_<engine>/config.py` | + `load_config(path, env)`, executor config fields. |
| `platforms/hermes/src/iops_hermes/model/client.py` | `ModelClient` Protocol + `StubModelClient` (+ real behind extra). |
| `platforms/hermes/src/iops_hermes/executor/api.py` | `ApiExecutor`: prompt → model → parse actions → sandboxed apply → evidence + budget. |
| `platforms/claude/src/iops_claude/runtime/client.py` | `RuntimeClient` Protocol + `StubRuntimeClient` (+ Claude Code adapter doc). |
| `platforms/claude/src/iops_claude/executor/hostruntime.py` | `HostRuntimeExecutor`: drive runtime → observe changes → result. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | `api_executor` / `host_executor` factory; budget wiring. |
| `platforms/hermes/tests/test_api_executor.py` | `ApiExecutor` over a `StubModelClient` (offline). |
| `platforms/claude/tests/test_host_executor.py` | `HostRuntimeExecutor` over a `StubRuntimeClient` (offline). |
| `platforms/<engine>/tests/test_budget.py` | Budget decisions + config loading. |
| `tests/conformance/test_budget.py` | Cross-engine budget-decision parity. |

## Step Sequence

### Task 1: Framework config + governance contracts

- [ ] **Step 1:** `CONFIG_CONTRACT.md` — common keys (`timeouts`, `budget`,
  `telemetry.otlp_endpoint`, `secrets` from env) + per-engine executor keys
  (`hermes`: `provider`/`model`/`api_base`; `claude`: `runtime`/`hooks`); file +
  env merge; no secrets in files.
- [ ] **Step 2:** `RESOURCE_GOVERNANCE.md` — `Budget {max_tokens, max_cost_usd,
  max_wall_s}`; `check(budget, usage) -> {allowed, reason}`; `BUDGET.*` codes;
  over-budget → task blocked (non-retriable).
- [ ] **Step 3:** registry — add both docs + `budget_root:
  framework/conformance/budget`.
- [ ] **Step 4: commit** — `feat: add config + resource-governance contracts`.

### Task 2: Budget vectors

- [ ] **Step 1:** `budget/under` (within all limits → allow);
  `budget/tokens` / `budget/cost` / `budget/time` (each limit exceeded → deny
  with its reason); `budget/unlimited` (all `None` → allow).
- [ ] **Step 2: commit** — `test: add budget decision vectors`.

### Task 3: Budget + config (engine-agnostic, both engines)

- [ ] **Step 1: failing tests** — `check` over the vectors; `load_config` merges
  file + env; secrets sourced from env, never the file.
- [ ] **Step 2:** `budget.py` (`Budget`, `check`) — identical in both engines.
- [ ] **Step 3:** extend `config.py` with `load_config` + executor config fields.
- [ ] **Step 4: green** (both engines) — `pytest`, `ruff`, `mypy --strict`.
  Commit `feat: add budget + config loader to hermes and claude`.

### Task 4: Hermes `ApiExecutor` (autonomous; offline via stub)

- [ ] **Step 1: failing tests** — `ApiExecutor` over a `StubModelClient`: canned
  response → parsed actions → sandboxed write + passing check → `success` with
  evidence; an over-scope action → sandbox-denied `failure`; over-budget →
  blocked. Fail.
- [ ] **Step 2:** `model/client.py` — `ModelClient` Protocol, `StubModelClient`;
  real `AnthropicClient`/`LiteLLMClient` behind `[anthropic]`/`[litellm]` extras
  (import-guarded, like OTel).
- [ ] **Step 3:** `executor/api.py` — `ApiExecutor(client, workspace, budget)`:
  `build_prompt(task)`, `client.complete`, `parse_actions(response)`, apply via
  effectors + `run_checks`, budget check, → `ExecutorResult`.
- [ ] **Step 4:** `engine.py` — `api_executor(...)` factory.
- [ ] **Step 5: green** — `pytest platforms/hermes`, `ruff`, `mypy --strict`.
  Commit `feat: add hermes ApiExecutor (autonomous, stub-tested)`.

### Task 5: Claude `HostRuntimeExecutor` (governor; offline via stub)

- [ ] **Step 1: failing tests** — `HostRuntimeExecutor` over a
  `StubRuntimeClient`: canned changed-files + output → `ExecutorResult`
  (touched_paths + evidence); failing runtime → `failure`. Fail.
- [ ] **Step 2:** `runtime/client.py` — `RuntimeClient` Protocol +
  `StubRuntimeClient`; document the real Claude Code hook adapter (env-specific).
- [ ] **Step 3:** `executor/hostruntime.py` — `HostRuntimeExecutor(client,
  workspace, budget)`: `client.run_task` → observe → `ExecutorResult`.
- [ ] **Step 4:** `engine.py` — `host_executor(...)` factory.
- [ ] **Step 5: green** — `pytest platforms/claude`, `ruff`, `mypy --strict`.
  Commit `feat: add claude HostRuntimeExecutor (governor, stub-tested)`.

### Task 6: Conformance

- [ ] **Step 1:** `test_budget.py` — cross-engine `check` parity over budget
  vectors; extend `test_registry` path check to `budget_root`.
- [ ] **Step 2: run full suite** + commit `test: add budget conformance`.

### Task 7: Version bump, changelog, handoff

- [ ] **Step 1:** atomic bump to `0.8.0`.
- [ ] **Step 2:** `CHANGELOG.md` `[0.8.0]`; update `HANDOFF.md`; plan `DONE`.
- [ ] **Step 3: full verification** + commit `chore: release spec v0.8.0
  (config, secrets & live executors)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green: budget decisions match `expect` in each engine + agree;
   all prior checks unchanged at `0.8.0`.
2. Per-engine tests (offline): `ApiExecutor` over a stub model produces real
   sandboxed edits + evidence and blocks over-scope/over-budget; `HostRuntimeExecutor`
   over a stub runtime records changes; budget + config loaders behave.
3. No network is required; real clients are skipped without credentials.
4. `ruff` + `mypy --strict` clean.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Live executors need network + keys → can't run in CI. | Pluggable transport + deterministic **stubs** (offline); real clients are extras behind credential-gated, skipped integration tests. |
| R2 | The two engines diverge → tempting to force parity. | By design (A/B, D-0013): live executors are **not** differential'd; only engine-agnostic **budget**/config-common is parity-pinned. |
| R3 | Prompt injection via model output. | Output is **data** — parsed into typed actions, applied through the sandbox; never executed as instructions (SECURITY_MODEL). |
| R4 | Runaway cost / loops on real calls. | `Budget` (tokens/cost/wall-time), checked before each model call; over-budget blocks the task; timeouts from config. |
| R5 | Budget wiring changes the shared loop and breaks scenarios. | Budgets are enforced **inside** the new executors; default unlimited; `MockExecutor` scenarios and the loop are untouched. |
| R6 | Secrets/keys leak into the repo. | Keys/secrets only from env; config files hold no secrets; stubs need no keys. |
| R7 | Optional extras (`anthropic`/`litellm`/otel) unavailable offline. | Import-guarded like OTel; absence degrades to stub/no-op; base deps stay `pyyaml`. |
| R8 | `parse_actions` mis-parses model output. | Strict typed parse (write/command schema); unknown/invalid → no action / `failure`; covered by stub tests. |

## Review log

> ≥2 passes before implementation.

### Pass 1 - 2026-05-24

- Finding: the `ApiExecutor` shouldn't reinvent apply/checks. Change: it parses
  model output into the **same action/check schema** as `ScriptedExecutor` and
  reuses the PLAN-004 effectors + evidence runner — the model is just the action
  generator PLAN-004 deferred.
- Finding: real model/host clients would break offline build + `mypy --strict`.
  Change: import-guarded (importlib, like the OTel provider), behind extras;
  absence degrades to the stub (R7).
- Finding: budgets span multiple tasks. Clarified: the executor instance (one per
  run) tracks cumulative usage and checks before each model call (R4/R5).
- Finding: forcing the divergent live executors into parity would be wrong.
  Confirmed (R2): they implement the same `Executor` Protocol but are A/B by
  design (D-0013) — not copied, not differential'd; only budget/config-common is
  parity-pinned.

### Pass 2 - 2026-05-24

- Finding: the wall-time budget dimension needs a usage source. Confirmed: the
  decision `check(budget, usage)` is pure (vector'd with given numbers); the live
  executor measures elapsed time at runtime (not vector'd) — same pure/real split
  as the rest.
- Finding: `ApiExecutor` does real file writes → not conformance-vector'd.
  Confirmed: it's per-engine offline-tested against a `StubModelClient` over a tmp
  workspace (PLAN-004 regime); only the budget decision is parity'd.
- Finding: budgets must not change the shared loop. Confirmed: enforced inside the
  executors; default `Budget` unlimited; the loop and `MockExecutor` scenarios are
  byte-identical (R5).
- Verification ↔ surface cross-check: budget (engine-agnostic) vector'd +
  differential; live executors per-engine stub-tested offline; real clients
  integration-only (credential-gated, skipped). No further findings.
