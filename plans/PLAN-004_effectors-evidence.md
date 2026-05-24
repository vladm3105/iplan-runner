# Effectors & Evidence Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** Make execution effects **real and safe** (Roadmap Phase 4 → `v0.4.0`).
PLAN-003's `MockExecutor` *simulated* touched paths and evidence; this plan adds
the **effector toolkit** an executor uses to actually do work: a **sandboxed**
file/command applier (path-jailed to `allowed_roots`, enforced *before* the
effect), an **evidence runner** that runs acceptance checks to produce real
evidence (the **"green"** half of done), and **secret redaction** for what lands
in the ledger/logs — plus a `ScriptedExecutor` that drives them.

**Architecture:** Additive (D-0014). New engine-agnostic contracts
(`framework/effectors/SANDBOX_CONTRACT.md`, `EVIDENCE_CONTRACT.md`) and a new
conformance kind for the **pure** path-jail decision
(`framework/conformance/sandbox/`). Each engine gains `effectors/`, `evidence/`,
`redaction.py`, and a `ScriptedExecutor`. Strict isolation (D-0011) holds. The
**safety-critical, pure** sandbox decision is pinned by golden vectors (D-0012);
real I/O (file writes, subprocesses) is per-engine unit/integration-tested and is
**not** placed in scenario vectors (it is side-effecting and non-deterministic).

**Tech Stack:** Python ≥3.11 (`subprocess`, `pathlib`); `pytest`; `unittest`
conformance; `ruff` + `mypy --strict`; YAML.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-004 |
| Depends on | `PLAN-001`..`PLAN-003` (DONE); D-0011..D-0014; Roadmap Phase 4 |
| Status     | IN REVIEW - 2026-05-24 |
| Feeds      | `PLAN-005` (saga/lease wrap real effects); `PLAN-008` (live executors generate the actions these effectors apply) |

## Objective

PLAN-003 records what an executor *says* it did. PLAN-004 lets an executor
actually do it, safely:

1. **Sandbox (enforce, don't just flag).** A **pure** `classify_path(path,
   allowed_roots) -> {allowed, reason}` (lexical normalization; deny absolute /
   `..`-escaping / out-of-roots) that gates every effect *before* it happens —
   the Phase-1 ledger validator only flagged violations after the fact.
2. **Effectors.** `apply_write(path, content, workspace)` and `run_command(cmd,
   workspace)` that perform real I/O **only** through the sandbox and inside the
   workspace.
3. **Evidence runner.** Execute a task's acceptance **checks** (commands),
   capture `{name, exit_code, output}` (redacted), and decide pass/fail — real
   evidence, the **"green"** half of "committed + green".
4. **Secret redaction.** A deterministic `redact(value, secrets)` applied to
   evidence/command output before it enters the ledger.
5. **`ScriptedExecutor`.** Drives effectors + evidence runner from a per-task
   action script (real edits/commands), proving the toolkit end-to-end and
   giving Phase-8 live executors the seam to plug into.

## Scope

**In:**

1. `framework/effectors/SANDBOX_CONTRACT.md` — path-jail semantics + reason codes
   (`SANDBOX.OK`, `SANDBOX.OUTSIDE_ROOTS`, `SANDBOX.ESCAPE`); the lexical
   decision is the parity surface.
2. `framework/effectors/EVIDENCE_CONTRACT.md` — acceptance-check → evidence
   mapping, pass/fail semantics, and redaction requirements.
3. `framework/conformance/sandbox/<name>/{input.yaml,expect.yaml}` +
   `sandbox_root` in the registry; engine-adapter contract gains
   `classify_path` + `scripted_executor`.
4. Per engine (`hermes`, `claude`, independent): `effectors/sandbox.py`
   (`classify_path`), `effectors/apply.py` (`apply_write`),
   `effectors/commands.py` (`run_command`), `evidence/runner.py` (`run_checks`),
   `redaction.py` (`redact`), `executor/scripted.py` (`ScriptedExecutor`);
   engine methods `classify_path`, `scripted_executor`; tests.
5. Conformance: `tests/conformance/test_sandbox.py` (cross-engine path-jail
   decision parity over `sandbox/` vectors); registry path check for `sandbox_root`.
6. Spec bump to `0.4.0`.

**Out:**

1. **Action generation** — *what* edits/commands to make is the live executor's
   job (Phase 8). `ScriptedExecutor` takes a pre-written action script.
2. Hardened sandbox (symlink/`realpath` resolution, resource limits), command
   allow-listing, prompt-injection defense, full secret management — Phase 7.
3. Saga wrapping of effects (retry/timeout/compensation) — PLAN-005.
4. Changing the run loop or scenario vectors — they keep using `MockExecutor`
   (deterministic). Real effectors are exercised by per-engine tests, not vectors.
5. VCS landing of the edits — Phase 6.

## Approach

**Two regimes, deliberately separated.**
- **Pure + parity-pinned:** `classify_path` is a lexical decision (no I/O) — the
  safety-critical core. It gets golden vectors and a cross-engine differential,
  exactly like other validators (D-0012). `redact` is also pure and
  unit-tested for identical behavior.
- **Side-effecting + per-engine-tested:** `apply_write`, `run_command`,
  `run_checks`, and `ScriptedExecutor` do real I/O against a **temp workspace**.
  They are unit/integration-tested per engine (write a file, run `python -c`,
  attempt an out-of-root write → denied). They are **not** scenario vectors —
  real filesystem/subprocess effects are non-deterministic and OS-specific, and
  scenario conformance must stay reproducible on the mock.

**Enforcement before effect.** `apply_write` / `run_command` call
`classify_path` on every target path first; a non-`OK` decision **raises**
before any write/exec. A `ScriptedExecutor` action that hits a denied path
yields `ExecutorResult(outcome="failure", reason="sandbox denied: …")`, so the
orchestrator blocks the task — the edit never happens. (Phase 1's
`ISOLATION.PATH_OUTSIDE_ROOTS` remains as a *post-hoc* ledger check; this is the
*preventive* layer.)

**Evidence is real.** `run_checks(checks, workspace)` runs each check command in
the workspace, captures exit code + (redacted) output, and returns
`{passed: all-zero-exit, results: [...]}`. The `ScriptedExecutor` turns that into
an `execution_evidence` entry and a `success`/`failure` outcome — so a completed
task now carries evidence of an actually-passing check.

**Redaction.** `redact(value, secrets)` replaces each known secret substring with
`"***"` (deterministic, order-independent on a sorted secret list). Applied to
command output before it is stored, so secrets never enter the append-only
ledger.

**`run` integration.** `iops-<engine> run` keeps `default_executor()` =
`MockExecutor` (no actions to perform without a live executor). A new
`run --actions <file> [--workspace DIR]` uses the `ScriptedExecutor` to perform
real effects, demonstrating the full path end-to-end.

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/effectors/SANDBOX_CONTRACT.md` | Path-jail semantics + `SANDBOX.*` reason codes (the parity surface). |
| `framework/effectors/EVIDENCE_CONTRACT.md` | Acceptance-check → evidence mapping, pass/fail, redaction. |
| `framework/conformance/sandbox/<name>/input.yaml` | `{path, allowed_roots}` decision input. |
| `framework/conformance/sandbox/<name>/expect.yaml` | `{allowed, reason}`. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + `sandbox_root`, + new protocol docs. |
| `platforms/<engine>/src/iops_<engine>/effectors/sandbox.py` | Pure `classify_path(path, allowed_roots)`. |
| `platforms/<engine>/src/iops_<engine>/effectors/apply.py` | `apply_write(path, content, workspace)` (sandbox-gated). |
| `platforms/<engine>/src/iops_<engine>/effectors/commands.py` | `run_command(cmd, workspace)` (subprocess). |
| `platforms/<engine>/src/iops_<engine>/evidence/runner.py` | `run_checks(checks, workspace)`. |
| `platforms/<engine>/src/iops_<engine>/redaction.py` | `redact(value, secrets)`. |
| `platforms/<engine>/src/iops_<engine>/executor/scripted.py` | `ScriptedExecutor(spec)` driving effectors + evidence. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | + `classify_path`, `scripted_executor`; capabilities `effect`/`evidence`. |
| `platforms/<engine>/src/iops_<engine>/cli/commands.py` | `run --actions/--workspace` path. |
| `platforms/<engine>/tests/test_effectors.py` | Sandbox decisions, real apply/command/evidence, redaction. |
| `tests/conformance/test_sandbox.py` | Cross-engine path-jail decision parity. |

## Step Sequence

### Task 1: Framework effector/evidence contracts

- [ ] **Step 1: `SANDBOX_CONTRACT.md`** — normalization (POSIX `normpath`); deny
  absolute paths and any path whose normalized form starts with `..`
  (`SANDBOX.ESCAPE`); allow when the normalized path equals `R` or starts with
  `R + "/"` for some normalized root `R` (`SANDBOX.OK`); otherwise
  `SANDBOX.OUTSIDE_ROOTS`. Note the lexical decision is the parity surface;
  `realpath`/symlink hardening is Phase 7.
- [ ] **Step 2: `EVIDENCE_CONTRACT.md`** — a task's `checks` are `{name,
  command}` where `command` is an **argument list** (no shell); evidence
  `passed` iff all exit 0; output is redacted; the executor maps this to an
  `execution_evidence` entry + outcome. Also document the `ScriptedExecutor`
  action-script schema: `{task_id: {actions: [{type: write, path, content} |
  {type: command, cmd: [..]}], checks: [{name, command: [..]}]}}`; `redact`
  processes secrets **longest-first** for determinism; secrets are sourced from
  the engine `Config` (default empty; real secret management is Phase 7).
- [ ] **Step 3: registry** — add both docs to `protocol_docs`; add
  `sandbox_root: framework/conformance/sandbox`.
- [ ] **Step 4: commit** — `feat: add sandbox + evidence contracts`.

### Task 2: Sandbox decision vectors

- [ ] **Step 1:** `sandbox/allow` (`src/a.py` under `["src/"]` → OK);
  `sandbox/outside` (`docs/x` under `["src/"]` → OUTSIDE_ROOTS);
  `sandbox/traversal` (`src/../../etc/x` → ESCAPE);
  `sandbox/absolute` (`/etc/x` → ESCAPE).
- [ ] **Step 2:** commit `test: add sandbox decision vectors`.

### Task 3: Hermes implementation (TDD)

- [ ] **Step 1: failing tests** — `classify_path` over the vectors; `apply_write`
  to a tmp workspace (and denied out-of-root → raises); `run_command` captures
  exit/output; `run_checks` pass/fail; `redact`; `ScriptedExecutor` end-to-end
  (write + passing check → success with evidence; denied path → failure). Fail.
- [ ] **Step 2: `effectors/sandbox.py`** — pure `classify_path`.
- [ ] **Step 3: `effectors/apply.py` + `commands.py`** — sandbox-gated write +
  `subprocess.run` in `workspace` (no shell; arg list), capture stdout/stderr.
- [ ] **Step 4: `redaction.py`** — `redact(value, secrets)`.
- [ ] **Step 5: `evidence/runner.py`** — `run_checks`, redacting output.
- [ ] **Step 6: `executor/scripted.py`** — `ScriptedExecutor(spec, workspace)`:
  apply actions via effectors (sandbox-gated, in order), run checks → evidence,
  return `ExecutorResult` (`touched_paths` = written paths; `failure` + reason on
  a denied path or failing check).
- [ ] **Step 7: `engine.py`** — `classify_path`, `scripted_executor`; extend
  `capabilities`. `cli/commands.py` — `run --actions <file> [--workspace DIR]`.
- [ ] **Step 8: green** — `pytest platforms/hermes -q`, `ruff`, `mypy --strict`.
  Commit `feat: add effectors + evidence to hermes`.

### Task 4: Claude implementation (independent)

- [ ] **Step 1–7:** mirror Task 3 as an independent copy under `iops_claude`;
  wire into `ClaudeEngine`. No import of `iops_hermes`.
- [ ] **Step 8: green** + commit `feat: add effectors + evidence to claude`.

### Task 5: Sandbox conformance

- [ ] **Step 1: `test_sandbox.py`** — for each `sandbox/` vector × importable
  engine: assert `engine.classify_path(input.path, input.allowed_roots)` equals
  `expect`; assert engines agree (differential). Skip rules as elsewhere.
- [ ] **Step 2:** extend `test_registry` path check to `sandbox_root`.
- [ ] **Step 3: run full suite** + commit `test: add sandbox conformance`.

### Task 6: Version bump, changelog, handoff

- [ ] **Step 1:** atomic bump to `0.4.0`.
- [ ] **Step 2:** `CHANGELOG.md` `[0.4.0]`; update `HANDOFF.md`; plan `DONE`.
- [ ] **Step 3: full verification** + commit `chore: release spec v0.4.0
  (effectors & evidence)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green: sandbox decisions match `expect` in each engine and engines
   agree; all prior checks still pass at `0.4.0`.
2. Per-engine tests: real `apply_write`/`run_command`/`run_checks` against a tmp
   workspace; out-of-root write denied *before* effect; `ScriptedExecutor`
   produces real evidence; `redact` removes secrets.
3. `ruff` + `mypy --strict` clean.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Real I/O can't be scenario-vector'd → parity gap. | The **pure** `classify_path` (safety core) is vector'd + differential; real I/O is per-engine tested. Scenario vectors stay on `MockExecutor`. |
| R2 | Lexical path-jail misses symlink escapes. | Baseline is lexical `normpath` (documented); `realpath`/symlink + resource limits are Phase 7. `apply_write` additionally rejects at write time. |
| R3 | `run_command` enables command injection. | No shell (`shell=False`, arg-list); cwd pinned to workspace; allow-listing + hardening Phase 7. Commands come from a trusted action script in Phase 4 (not yet model-generated). |
| R4 | Secrets leak into the append-only ledger. | `redact` applied to all captured output before storage; deterministic; unit-tested. |
| R5 | Subprocess non-determinism in tests. | Tests use trivial, hermetic commands (`python -c`); no network; tmp workspace. |
| R6 | Scope creep into action generation. | `ScriptedExecutor` consumes a pre-written script; model/host action generation is Phase 8 (explicit Out). |
| R7 | `classify_path` cross-engine drift. | Single documented algorithm (normpath + prefix); golden vectors + differential enforce parity. |
| R8 | A multi-action task that fails mid-way leaves partial effects (earlier writes persist). | Acknowledged for Phase 4; the task is `blocked`, and **compensation/rollback of partial effects is PLAN-005** (saga). Documented so it isn't mistaken for completeness. |

## Review log

> ≥2 passes before implementation.

### Pass 1 - 2026-05-24

- Finding: "under an allowed_roots prefix" was imprecise (`src` would match
  `source/`). Change: exact rule — normalized path equals `R` or starts with
  `R + "/"` (Task 1 Step 1).
- Finding: the `ScriptedExecutor` action-script schema, command format, and
  secret source were unspecified. Change: documented the schema, `command` as an
  argument list (no shell), and secrets sourced from `Config` (Task 1 Step 2).
- Finding: `ScriptedExecutor` needs a workspace. Change: `ScriptedExecutor(spec,
  workspace)`; `run --workspace` supplies it (Task 3 Step 6 / Approach).
- Finding: `redact` could be non-deterministic with overlapping secrets. Change:
  process secrets longest-first.
- Finding: the `SANDBOX.*` reason codes are decision outputs, not document
  `validate()` findings — confirmed they stay out of `rule-ids.yaml` (which is
  for validators) and live in `SANDBOX_CONTRACT.md`; conformance compares them
  directly via `test_sandbox`. No change.

### Pass 2 - 2026-05-24

- Finding: partial effects on a mid-task failure aren't rolled back here. Added
  R8 — the task blocks, and compensation is PLAN-005; documented so Phase 4 isn't
  mistaken for transactional.
- Finding: real I/O must not enter scenario vectors or the differential. Confirmed
  — scenario vectors keep using `MockExecutor`; only the pure `classify_path` is
  vector'd (R1); the effector/evidence tests are per-engine and use a tmp
  workspace + hermetic `python -c` commands (R5).
- Verification ↔ surface cross-check: the parity-critical surface (`classify_path`)
  has 4 vectors + differential; real effectors have per-engine apply/command/
  evidence/redaction tests incl. the denied-write path. No further findings.
