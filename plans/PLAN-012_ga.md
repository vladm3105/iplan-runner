# GA (v1.0.0) Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** Cut **`v1.0.0`** (Roadmap Phase 12). GA is consolidation, not new
runtime: a **worked end-to-end example** proving the full pipeline reaches
**committed + green + monitored** on **both engines**, a **security review**,
**docs**, a **hardening** pass, and a **contract-stability** commitment. Per the
owner's call, GA ships **without a LICENSE** and **without packaging/distribution**
(both tracked in `TODO.md` for later).

**Architecture:** No contract or runtime changes — GA exercises and documents what
phases 1–11 built. The new artifact is an offline, deterministic **acceptance
test** (per engine) that drives the whole stack; everything else is docs +
review. The `framework/` contract is declared **stable** at `1.0.0` (SemVer:
breaking contract changes bump major).

**Tech Stack:** Python ≥3.11 (`git`, `subprocess`); `pytest`; `unittest`
conformance; `ruff` + `mypy --strict`; Markdown.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-012 |
| Depends on | `PLAN-001`..`PLAN-011` (DONE); D-0011..D-0015; Roadmap Phase 12 |
| Status     | IN REVIEW - 2026-05-24 |
| Feeds      | post-`v1.0` work (codex/vertexai, issue loop, multi-tenant); deferred parallel track (LICENSE, CI, packaging) |

## Objective

Prove the framework works end-to-end and declare it stable:

1. **Worked example.** A reference SDD-IPLAN + an action script + a monitoring
   manifest under `examples/`, with a documented walkthrough.
2. **End-to-end acceptance.** A per-engine test that runs the full pipeline on
   the example — ingest → run (real edits in a tmp git workspace, via
   `ScriptedExecutor`) → land (commit + sign) → handover → monitor — and asserts
   **committed + green + monitored + signed**, on **both** engines.
3. **Security review.** `SECURITY.md` (disclosure) + `docs/SECURITY_REVIEW.md`
   walking the threat model and confirming each mitigation is wired; residual
   risks recorded.
4. **Docs.** `docs/GETTING_STARTED.md` tying the phases together; README updated
   with the `v1.0.0` capability set + the contract-stability statement.
5. **Hardening.** A verification pass: full green, version parity, no stub/TODO
   leaks in shipped `src/`, conformance covers every surface.
6. **Release `v1.0.0`.**

## Scope

**In:**

1. `examples/` — `IPLAN-EXAMPLE.yaml` (approved SDD-IPLAN shape), `actions.yaml`
   (per-task write + passing check), `monitoring.yaml` (manifest bound to the
   example), `README.md` (walkthrough using the engine CLIs).
2. `platforms/<engine>/tests/test_acceptance.py` — the full-pipeline acceptance
   test (both engines, offline/deterministic, real git in a tmp workspace).
3. `SECURITY.md` + `docs/SECURITY_REVIEW.md`.
4. `docs/GETTING_STARTED.md`; README update (capabilities + contract stability).
5. Hardening checklist run (no code changes expected).
6. `v1.0.0` bump; `CHANGELOG` `[1.0.0]`; `ROADMAP` Phase 12 done; `HANDOFF`/`TODO`.

**Out:**

1. **LICENSE** — owner deferred; tracked in `TODO.md` (do not add a license).
2. **Packaging / distribution / PyPI / containers** — owner deferred; tracked.
3. New runtime or contract features — GA is consolidation only.
4. Live executor / real-network paths in the acceptance test — it uses
   `ScriptedExecutor` (real local edits/commands) + a test signing key; no
   network/credentials.

## Approach

**The acceptance test is the GA proof.** For each engine, in a tmp **git repo**
workspace, with an injected clock/ids and a test signing key:

1. `ingest_iplan(examples/IPLAN-EXAMPLE.yaml)` → validate (pass).
2. `run(manifest, scripted_executor(actions, workspace), …)` → tasks execute real
   edits + a passing check → completed, reconciled, gate passed (**green**).
3. `land(ledger, workspace, branch=…, actor=operator)` → real commit recorded +
   `sign_ledger` (**committed + signed**); `verify_ledger` is true.
4. `build_handover(...)` → `status: completed` with a `commit` (committed +
   green).
5. `evaluate_alerts(monitoring.yaml, healthy samples)` → `[]`;
   `emit_run_telemetry` records run signals (**monitored**).

Asserts the committed + green + monitored end state on **both** engines. Both use
the shared **`ScriptedExecutor`** (deterministic *real* edits) — the right tool
for an offline acceptance; the divergent live executors (`ApiExecutor` /
`HostRuntimeExecutor`) generate actions and are integration-only, already covered
by their PLAN-008 stub tests. Signing is enabled via the engine's
`Config.signing_key` (a test key) so `land` auto-signs. It is real I/O (git,
subprocess) so it lives per-engine (not a pure conformance vector) and is
deterministic offline — the GA acceptance criterion, not a parity check
(cross-engine parity is already proven by the scenario/chain/decision differentials).

**Security review = evidence, not new code.** `docs/SECURITY_REVIEW.md` walks the
`SECURITY_MODEL` threat table and points at the wired mitigation + its test for
each (hash chain + HMAC signing; sandbox lexical + realpath; redaction; layered
authz; budgets; untrusted-output). Residual risks are recorded: ledger schema
migration (G10), full auth-provider wiring (D-0015), deferred LICENSE/packaging.
`SECURITY.md` gives a disclosure path.

**Contract stability at 1.0.0.** README/CHANGELOG state that from `v1.0.0` the
`framework/` contract is stable under SemVer: additive changes are minor;
breaking contract changes bump major. The conformance suite is the gate.

**Hardening is a checklist, not edits.** Confirm: full verify green; the four
version markers + registry `spec_version` all equal `1.0.0`; no `TODO`/`FIXME`/
stub-`raise NotImplementedError` in shipped `src/` (except documented
integration-only seams); every conformance root resolves; both engines isolated.

## File Structure

| Path | Responsibility |
|------|----------------|
| `examples/IPLAN-EXAMPLE.yaml` | Approved SDD-IPLAN-shaped input for the walkthrough. |
| `examples/actions.yaml` | Per-task action script (write + check) for the ScriptedExecutor. |
| `examples/monitoring.yaml` | Monitoring manifest bound to the example IPLAN/ledger. |
| `examples/README.md` | End-to-end walkthrough using `iops-<engine>` CLIs. |
| `platforms/<engine>/tests/test_acceptance.py` | Full-pipeline acceptance (committed + green + monitored + signed). |
| `SECURITY.md` | Responsible-disclosure pointer + `SECURITY_MODEL` link. |
| `docs/SECURITY_REVIEW.md` | Threat-model walk: mitigation + test per threat; residual risks. |
| `docs/GETTING_STARTED.md` | Phase-by-phase usage guide. |
| `README.md` | + `v1.0.0` capabilities + contract-stability statement. |

## Step Sequence

### Task 1: Worked example

- [ ] **Step 1:** `examples/IPLAN-EXAMPLE.yaml` — SDD-IPLAN shape (document_control,
  `exec_ready` ≥ 90, isolation_scope, 2 tasks).
- [ ] **Step 2:** `examples/actions.yaml` (per-task write + passing check) +
  `examples/monitoring.yaml` (manifest bound to the example).
- [ ] **Step 3:** `examples/README.md` — walkthrough (`intake`, `run --actions
  --land`, `verify --key`, monitoring) for both engines.
- [ ] **Step 4: commit** — `docs: add worked example`.

### Task 2: End-to-end acceptance test (both engines)

- [ ] **Step 1:** `platforms/hermes/tests/test_acceptance.py` — drive the full
  pipeline on the example in a tmp git repo (injected clock/ids + test key);
  assert intake passes, run is green + reconciled, `land` commits + signs,
  `verify_ledger` true, handover `completed` with a `commit`, alerts empty.
- [ ] **Step 2:** mirror as `platforms/claude/tests/test_acceptance.py`
  (independent; also via `scripted_executor` — real edits → committed + green —
  reaching the same end state).
- [ ] **Step 3: green** — `pytest platforms/hermes platforms/claude -q`. Commit
  `test: add end-to-end acceptance on both engines`.

### Task 3: Security review

- [ ] **Step 1:** `docs/SECURITY_REVIEW.md` — for each `SECURITY_MODEL` threat,
  the wired mitigation + its test; residual risks (G10, D-0015, deferred
  LICENSE/packaging).
- [ ] **Step 2:** `SECURITY.md` — disclosure path + link to the model/review.
- [ ] **Step 3: commit** — `docs: add security review + SECURITY.md`.

### Task 4: Docs + contract stability

- [ ] **Step 1:** `docs/GETTING_STARTED.md` — phase-by-phase usage.
- [ ] **Step 2:** README — `v1.0.0` capability set + the contract-stability
  statement (SemVer over `framework/`).
- [ ] **Step 3: commit** — `docs: add getting-started + contract-stability`.

### Task 5: Hardening verification

- [ ] **Step 1:** run the full verify (conformance + pytest + ruff + mypy);
  confirm green.
- [ ] **Step 2:** grep shipped `src/` for `TODO`/`FIXME`/`NotImplementedError`
  (only the documented integration-only seam may remain — `model/client.py`'s
  `get_model_client` for an unsupported provider) + confirm version-marker parity
  + every conformance root resolves + isolation.
- [ ] **Step 3: commit** (if any doc/nit fixes) — `chore: GA hardening pass`.

### Task 6: Release v1.0.0

- [ ] **Step 1:** bump all markers to `1.0.0` (framework/VERSION, registry
  spec_version, both engines' FRAMEWORK_SPEC_VERSION + package versions).
- [ ] **Step 2:** `CHANGELOG` `[1.0.0]`; `ROADMAP` Phase 12 → complete; update
  `HANDOFF` + `TODO`.
- [ ] **Step 3: full verification** + commit `chore: release v1.0.0 (GA)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green; per-engine tests green incl. **acceptance** (both engines
   reach committed + green + monitored + signed on the example).
2. Version markers + registry `spec_version` all `1.0.0`; no stub/TODO leaks
   beyond the documented integration seam; every conformance root resolves.
3. `ruff` + `mypy --strict` clean.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Acceptance test is real I/O (git/subprocess) → flaky/conformance-unfit. | Per-engine (not pure conformance); tmp git repo + hermetic `python -c` checks; injected clock/ids + test key; no network. |
| R2 | GA implies a license / distribution that the owner deferred. | Explicitly **out** (owner's call); recorded in `TODO.md`; GA ships neither. |
| R3 | Declaring 1.0.0 over-commits a still-evolving contract. | Stability is over `framework/` under SemVer (major for breaking); conformance is the gate; runtime internals may still evolve within the contract. |
| R4 | Security review claims coverage that isn't wired. | Each threat row cites the mitigation **and its test**; residual/deferred items are named (not hidden). |
| R5 | The example drifts from the engines. | The acceptance test runs *on the example*, so drift fails CI; the example is executable, not just prose. |
| R6 | claude has no ApiExecutor / its host-runtime stub doesn't write files. | Both engines run the acceptance via the shared `ScriptedExecutor` (real edits → committable); the divergent live executors are integration-only (PLAN-008). The acceptance asserts the *outcome*, not the executor. |

## Review log

> ≥2 passes before implementation.

### Pass 1 - 2026-05-24

- Finding (bug): claude's `HostRuntimeExecutor` stub *reports* changed files but
  doesn't write them, so `land` would find a clean tree → nothing to commit → not
  "committed". Change: both engines run the acceptance via the shared
  `ScriptedExecutor` (real edits); the divergent live executors are
  integration-only (PLAN-008), not the offline acceptance path (R6, Task 2 Step 2).
- Finding: signing must be enabled for `land` to auto-sign. Clarified: the test
  sets `Config.signing_key` (a test key); `land` then signs and `verify_ledger`
  confirms.
- Finding: the hardening grep would flag a legitimate seam. Named the allowed
  exception: `model/client.py` `get_model_client` (`NotImplementedError` for an
  unsupported provider).
- Finding: GA must not imply license/distribution. Reconfirmed both are **out**
  (owner deferred) and tracked in `TODO.md` (R2).

### Pass 2 - 2026-05-24

- Finding: an executable example prevents doc drift. Confirmed the acceptance runs
  *on the `examples/` artifacts*, so drift fails the build (R5).
- Finding: 1.0.0 over-commitment. Confirmed stability is scoped to the
  `framework/` contract under SemVer (breaking → major), gated by conformance;
  runtime internals may still evolve within the contract (R3).
- Finding: the security review must be evidence-backed. Confirmed each threat row
  cites the wired mitigation **and its test**, and names residual/deferred items
  (G10 migration, D-0015 full auth, deferred LICENSE/packaging) (R4).
- Verification ↔ surface cross-check: GA adds no contract/runtime; the acceptance
  test is the new artifact (per-engine, offline, deterministic); everything else
  is docs + a verification pass. No further findings.
