# Landing & VCS Integration Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** Deliver the **"committed"** half of "committed + green" (Roadmap Phase
6 → `v0.6.0`). After a run is green and reconciled, **land** the workspace
changes to a git **branch + commit**, record the commit in the ledger, and let
the gate **require** a commit before a landed ledger is considered complete.

**Architecture:** Additive (D-0014). Extends the ledger contract
(`ledger_control.requires_landing` + a `vcs` section), adds a VCS effector and a
post-run `land()` step, and one conditional gate rule (`LEDGER.NOT_COMMITTED`).
Two-regime parity (as PLAN-004/005): the **pure** `NOT_COMMITTED` decision is
golden-vector'd + differential; **real git** is per-engine tested (SHAs are
non-deterministic). Prior phases are unaffected — the rule only fires when a
ledger sets `requires_landing`, which no existing scenario does.

**Tech Stack:** Python ≥3.11 (`subprocess` + `git`); `pytest`; `unittest`
conformance; `ruff` + `mypy --strict`; YAML.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-006 |
| Depends on | `PLAN-001`..`PLAN-005` (DONE); D-0011..D-0014; Roadmap Phase 6 |
| Status     | IN REVIEW - 2026-05-24 |
| Feeds      | `PLAN-009` (operator approval before landing); the SDD "done when committed + green" closure |

## Objective

PLAN-004/005 apply real edits and prove them green, but nothing commits them.
PLAN-006 lands the work:

1. **VCS effector** — `commit_all(workspace, branch, message, author) -> sha` and
   `head_sha` over a real git repo (per-engine tested).
2. **Landing step** — `land(ledger, workspace, ...)`: commit the workspace to a
   branch, append a commit record to the ledger's `vcs` section + a `commit`
   execution-log event, mark `ledger_control.requires_landing = true`, and
   re-run the gate (now satisfied).
3. **Commit-required gate rule** — `LEDGER.NOT_COMMITTED` (GATE-LEDGER-006) fires
   **only** when `requires_landing` is true and no commit is recorded. So a
   landed ledger is "complete" only when **committed + green**; non-landing runs
   are unchanged.
4. **Handover** — the receipt carries the landing `commit` (sha + branch).
5. **CLI** — `run --land --branch <b>`: run, and **only if green + reconciled**,
   land (never commit broken work).

## Scope

**In:**

1. `framework/execution/IPLAN-LEDGER-TEMPLATE.yaml` — add
   `ledger_control.requires_landing` (default absent/false) and a `vcs` section
   (`branch`, `commits: [{sha, message, at, touched_paths}]`).
2. `framework/execution/IPLAN-VERIFY-TEMPLATE.yaml` — add `GATE-LEDGER-006`
   (→ `LEDGER.NOT_COMMITTED`). `framework/vcs/LANDING_CONTRACT.md` — landing
   semantics. Rule-ID catalog + `RULE-IDS.md` + registry updated.
3. Golden vectors: `ledger/committed` (requires_landing + commit → pass),
   `ledger/not_committed` (requires_landing, no commit → fail).
4. Per engine (`hermes`, `claude`, independent): `vcs/git.py`
   (`commit_all`, `head_sha`, `current_branch`), `LEDGER.NOT_COMMITTED` in the
   ledger validator, `GATE-LEDGER-006` in `default_gate()`, `land()` engine
   method, handover `commit` field, CLI `run --land --branch`; tests (real git).
5. Conformance: `NOT_COMMITTED` covered by existing vector replay; rule-catalog
   coverage; prior scenarios unchanged.
6. Spec bump to `0.6.0`.

**Out:**

1. **Push / open a PR** to a remote — needs remote + auth (GitHub-specific). The
   framework records the local commit; pushing/PR is operator/CI integration
   (a later phase / out of scope here).
2. Merge-conflict resolution, rebasing — the workspace is assumed clean for the
   run (single-branch landing).
3. Live executors generating the edits — Phase 8 (here `ScriptedExecutor` /
   real edits from PLAN-004 are what gets committed).

## Approach

**`requires_landing` makes the rule opt-in (keeps prior phases green).**
`LEDGER.NOT_COMMITTED` fires iff `ledger_control.requires_landing` is true **and**
`vcs.commits` is empty. Existing ledgers/scenarios never set `requires_landing`,
so the rule never fires for them — `GATE-LEDGER-006` can live in the default gate
safely, and all PLAN-003/004/005 scenarios pass unchanged.

**`run()` is unchanged; `land()` is a post-step.** `engine.run(...)` still gates
well-formedness ("green"); it does **not** set `requires_landing`. The CLI then,
**only when the run is green and reconciled**, calls `engine.land(...)`, which:
commits the workspace, appends the commit record + a `commit` event, sets
`requires_landing = true`, and **re-runs the gate** (now committed → passes).
This avoids the chicken-and-egg of requiring a commit before one exists, and
never commits work that failed the gate.

**Two regimes.** `LEDGER.NOT_COMMITTED` is a pure ledger check → golden vectors +
cross-engine differential. `git.commit_all` is real I/O with non-deterministic
SHAs → per-engine tested against a tmp git repo (assert a commit exists, the
ledger records its sha/branch, the working tree is clean), **not** scenario
vectors or differential.

**`NOT_COMMITTED` is a guard, not a live trip-wire.** In the live flow `land()`
always commits *before* setting `requires_landing`, so the rule never fires for
a real landed run. Its job is to reject **external / hand-crafted** ledgers that
*claim* `requires_landing` without a commit — exactly what the golden vectors
exercise.

**No-op landing when there's nothing to commit.** `land()` first checks
`git.has_changes(workspace)`; if the working tree is clean (e.g. a `MockExecutor`
run that touched nothing) it is a **no-op** — no commit, `requires_landing` stays
false, the green handover is unchanged. Real changes (from `--actions` /
PLAN-004 edits) are what gets committed. `run --land` therefore pairs naturally
with `--workspace` pointing at a git repo and `--actions` producing edits.

**Handover carries the commit.** `build_handover_receipt` adds an optional
`commit` (`{sha, branch}`) read from the ledger's last `vcs` commit; the handover
validator is unchanged (commit enforcement lives in the gate, so prior handover
vectors are unaffected).

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/execution/IPLAN-LEDGER-TEMPLATE.yaml` | + `ledger_control.requires_landing`, + `vcs` section. |
| `framework/execution/IPLAN-VERIFY-TEMPLATE.yaml` | + `GATE-LEDGER-006`. |
| `framework/vcs/LANDING_CONTRACT.md` | Landing semantics + commit record shape + the committed-required rule. |
| `framework/conformance/rule-ids.yaml` + `RULE-IDS.md` | + `LEDGER.NOT_COMMITTED`. |
| `framework/conformance/vectors/ledger/{committed,not_committed}/` | New golden vectors. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + `LANDING_CONTRACT.md` protocol doc. |
| `platforms/<engine>/src/iops_<engine>/vcs/git.py` | `commit_all`, `head_sha`, `current_branch`. |
| `platforms/<engine>/src/iops_<engine>/validation/ledger_rules.py` | + `LEDGER.NOT_COMMITTED`. |
| `platforms/<engine>/src/iops_<engine>/orchestrator/loop.py` | `default_gate()` + `GATE-LEDGER-006`; `land(...)`. |
| `platforms/<engine>/src/iops_<engine>/handover/receipt.py` | + `commit` field. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | `land(...)` adapter method. |
| `platforms/<engine>/src/iops_<engine>/cli/commands.py` | `run --land --branch`. |
| `platforms/<engine>/tests/test_vcs.py` | Real git commit + landing + gate-requires-commit. |

## Step Sequence

### Task 1: Framework landing contract

- [ ] **Step 1:** ledger template — `ledger_control.requires_landing: false` +
  a `vcs` section (`branch`, `commits: [{sha, message, at, touched_paths}]`).
- [ ] **Step 2:** verify template — `GATE-LEDGER-006` → `LEDGER.NOT_COMMITTED`;
  rule-ids catalog + `RULE-IDS.md` entry (IPLAN-007, error).
- [ ] **Step 3:** `framework/vcs/LANDING_CONTRACT.md` — landing flow (commit only
  when green + reconciled), commit record shape, the `requires_landing`-gated
  rule, and the out-of-scope push/PR note. Registry → add the doc.
- [ ] **Step 4: parse check + commit** — `feat: add landing/VCS contract`.

### Task 2: Golden vectors

- [ ] **Step 1:** `ledger/committed` — a valid completed ledger with
  `requires_landing: true` and one `vcs.commits` entry → `pass`.
- [ ] **Step 2:** `ledger/not_committed` — same but `vcs.commits: []` →
  `fail` `[LEDGER.NOT_COMMITTED]`.
- [ ] **Step 3: commit** — `test: add committed/not_committed vectors`.

### Task 3: Hermes implementation (TDD)

- [ ] **Step 1: failing tests** — `LEDGER.NOT_COMMITTED` (requires_landing +/-
  commit); `git.commit_all` in a tmp repo → sha + clean tree; `land()` records
  the commit, sets `requires_landing`, re-gates to passed; `run --land` end to
  end (scripted write → committed). Fail.
- [ ] **Step 2: `validation/ledger_rules.py`** — add the rule (fires iff
  `requires_landing` and no `vcs.commits`).
- [ ] **Step 3: `loop.py` `default_gate()`** — add `GATE-LEDGER-006`.
- [ ] **Step 4: `vcs/git.py`** — `commit_all` (`git -C ws switch -c branch`,
  `add -A`, `commit -m` with explicit author env), `head_sha`, `current_branch`,
  `has_changes`.
- [ ] **Step 5: `land()` in `loop.py` + `engine.py`** — no-op if
  `not has_changes`; else commit, append commit record + `commit` event, set
  `requires_landing`, re-run gate, return `RunResult`.
- [ ] **Step 6: `handover/receipt.py`** — add optional `commit` (`{sha, branch}`)
  from the last `vcs` commit; update the receipt template + HANDOVER contract
  (validator unchanged).
- [ ] **Step 7: `cli/commands.py`** — `run --land --branch <b>` (uses
  `--workspace`): run, then `land` iff `gate == passed` and reconciled.
- [ ] **Step 8: green** — `pytest`, `ruff`, `mypy --strict`. Commit
  `feat: add landing/VCS to hermes`.

### Task 4: Claude implementation (independent)

- [ ] **Step 1–7:** mirror Task 3 as an independent copy. No import of `iops_hermes`.
- [ ] **Step 8: green** + commit `feat: add landing/VCS to claude`.

### Task 5: Conformance

- [ ] **Step 1:** confirm the new ledger vectors replay through every engine
  (existing `test_vectors`); rule-catalog coverage includes `LEDGER.NOT_COMMITTED`.
- [ ] **Step 2: run full suite** + commit `test: confirm landing conformance`.

### Task 6: Version bump, changelog, handoff

- [ ] **Step 1:** atomic bump to `0.6.0`.
- [ ] **Step 2:** `CHANGELOG.md` `[0.6.0]`; update `HANDOFF.md`; plan `DONE`.
- [ ] **Step 3: full verification** + commit `chore: release spec v0.6.0
  (landing & VCS)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green: `committed`/`not_committed` vectors yield the expected
   rule-ID set in each engine + agree; all prior checks (incl. unchanged
   scenarios) pass at `0.6.0`.
2. Per-engine tests: `git.commit_all` makes a real commit (clean tree, sha);
   `land()` records it, sets `requires_landing`, re-gates to passed; `run --land`
   produces a committed + green handover; a non-green run is **not** landed.
3. `ruff` + `mypy --strict` clean.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | A commit-required rule breaks all prior scenarios. | The rule is gated on `requires_landing` (absent in every existing ledger/scenario); it can live in the default gate as a no-op for them. |
| R2 | Real git is non-deterministic (SHAs) → can't be vector'd. | `NOT_COMMITTED` is a pure check (vector'd + differential); real git is per-engine tested (assert commit exists + recorded, not exact SHA). |
| R3 | Landing commits broken work. | `land()` runs only when the run is green + reconciled; the CLI gates on `gate == passed`. |
| R4 | git unavailable in CI. | git is present in the toolchain; tests `git init` a tmp repo and set explicit author env; no network/remote needed. |
| R5 | Scope creep into push/PR/remotes. | Out of scope — local branch + commit only; push/PR is operator/CI integration, documented in the contract. |
| R6 | `git commit` global identity missing → failure. | `commit_all` passes explicit `GIT_AUTHOR_*` / `-c user.*` (no reliance on global git config). |
| R7 | Chicken-and-egg: gate requires a commit that doesn't exist yet. | `run()` gates without `requires_landing`; `land()` commits then sets the flag and re-gates. |
| R8 | `run --land` with no file changes → `git commit` fails ("nothing to commit"). | `land()` is a no-op when `has_changes` is false; `requires_landing` stays false, handover green/unchanged. |

## Review log

> ≥2 passes before implementation.

### Pass 1 - 2026-05-24

- Finding: `run --land` with `MockExecutor` (no file changes) would make
  `git commit` fail ("nothing to commit"). Change: `land()` is a no-op when
  `git.has_changes` is false (R8); pairs with `--workspace` + `--actions`.
- Finding: the live flow never actually trips `NOT_COMMITTED` (land commits
  before setting the flag). Clarified its role as a **guard** for external /
  hand-crafted ledgers — which is what the vectors test.
- Finding: the handover receipt + template needed the `commit` field documented,
  but the handover validator must stay unchanged (else prior handover vectors
  break). Stated: commit enforcement is in the gate, the receipt field is
  informational.
- Finding: `commit_all` must not depend on global git identity. Change: pass
  explicit author env / `-c user.*` (R6).

### Pass 2 - 2026-05-24

- Finding: real git is non-deterministic, so it stays out of scenario vectors /
  differential; only the pure `NOT_COMMITTED` check is vector'd (R2). Confirmed
  the new ledger vectors reuse a valid base + `requires_landing`/`vcs` so each
  isolates exactly its rule (PLAN-001 discipline).
- Finding: adding `requires_landing` + `vcs` to the ledger template is additive
  and doesn't affect `test_contract` (parse + document_type) or prior scenarios
  (which never set `requires_landing`). Confirmed prior phases stay green (R1).
- Verification ↔ surface cross-check: `NOT_COMMITTED` has committed/not_committed
  vectors + differential; real landing (`commit_all`/`land`/`run --land`) is
  per-engine tested incl. the no-change no-op. No further findings.
