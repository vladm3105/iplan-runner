# Session Handoff

> Sessions run in ephemeral containers. **Only committed + pushed work
> survives.** Keep this file current before stopping or switching context.

## Current state - 2026-05-23

- Branch: `claude/iplan-execution-framework-jc03k`
- Phase: **PLAN-001 implemented** (SDD workflow: plan → 4 review passes →
  implement → verify → land).
- Repo decisions captured in `plans/DECISIONS.md` (D-0001..D-0012; D-0007
  superseded by D-0011).
- `plans/PLAN-001_iplan-execution-ledger-runtime.md` — **DONE** (`v0.1.0`).
- `plans/PLAN-002_iplan-intake-handover.md` — **DONE** (`v0.2.0`): IPLAN intake
  (normalize SDD IPLAN → `iplan-intake` manifest) + handover receipt contracts,
  per-engine readers/validators/builders, reader-parity conformance.
- `plans/PLAN-003_execution-core-run-loop.md` — **DONE** (`v0.3.0`): orchestrator
  + task state machine, pluggable `Executor` + `MockExecutor`, durable ledger
  persistence + status/query, gate-as-veto, `iops-<engine> run`/`status`, and
  scenario-vector conformance (projection + cross-engine differential).
- `plans/PLAN-004_effectors-evidence.md` — **DONE** (`v0.4.0`): sandbox/evidence
  contracts, pure `classify_path` (vector'd), sandboxed `apply_write`/
  `run_command`, evidence runner, secret redaction, and a `ScriptedExecutor`
  performing real effects; sandbox conformance.
- `plans/PLAN-005_saga-lease-runtime.md` — **DONE** (`v0.5.0`): saga runtime
  (bounded retry/backoff, idempotency, compensation undoing partial writes,
  escalation) + lease lifecycle (`can_acquire`/`renew`/state); saga scenarios +
  lease vectors.
- `plans/PLAN-006_landing-vcs.md` — **DONE** (`v0.6.0`): landing/VCS — `land()`
  commits a green+reconciled run to a git branch, records it in the ledger,
  `LEDGER.NOT_COMMITTED` (requires_landing-gated) lets the gate require
  committed + green; handover commit field; `run --land`.
- `plans/PLAN-007_security-ledger-integrity.md` — **DONE** (`v0.7.0`): security
  model + authenticated ledger (`sign_ledger`/`verify_ledger`, HMAC over canonical
  event), role-based `authorize`, realpath sandbox hardening; signing/authz
  vectors. Agent-first auth direction recorded in D-0015.
- `plans/PLAN-008_config-live-executors.md` — **DONE** (`v0.8.0`): config +
  secrets (`load_config`), resource governance (`Budget`/`check`), and the first
  live executors — hermes `ApiExecutor` (autonomous) + claude `HostRuntimeExecutor`
  (governor), the A/B divergence (D-0013); offline stub-tested, real clients
  integration-only. Next: `PLAN-009` (human-in-the-loop & operator control).

## What landed (slice 1)

Hybrid spec + runtime with **strict engine isolation** (D-0011):

- `framework/` — engine-agnostic contract: execution ledger / verify-gate /
  chain / audit templates + protocol docs, OTel monitoring manifest,
  engine-adapter contract, registry, rule-ID catalog (20 rules), 24 golden
  vectors.
- `platforms/hermes/` + `platforms/claude/` — two fully self-contained engines
  (no shared code), each with ledger store + hash chain, validators, gate
  runner, audit generation, OTel-optional monitoring, SLO eval, CLI.
- `tests/conformance/` — vector replay + cross-engine differential + strict
  isolation + catalog coverage + spec parity.

## Verification (all green)

```
python -m unittest discover -s tests/conformance -v   # 14 passed
pytest platforms/hermes platforms/claude -q            # 57 passed
ruff check platforms                                   # clean
mypy --strict platforms/hermes/src platforms/claude/src  # clean
```

## Repo CI — install manually (App lacks `workflows` permission)

The automation token cannot push files under `.github/workflows/`. Add this
workflow via the GitHub web UI (**Actions → New workflow → set up a workflow
yourself**) or commit it from a context with `workflows` permission. Save as
`.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: ["**"]
  pull_request:
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install engines (editable, with dev extras)
        run: pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
      - name: Conformance (vector replay + isolation + parity)
        run: python -m unittest discover -s tests/conformance -v
      - name: Engine tests
        run: pytest platforms/hermes platforms/claude -q
      - name: Lint
        run: ruff check platforms
      - name: Types
        run: mypy --strict platforms/hermes/src platforms/claude/src
```

## Backlog (post slice 1)

- `platforms/codex/`, `platforms/vertexai/` engines (own plans).
- Live Claude Code hook wiring for the `claude` engine.
- Fuller OTel provider (metrics/logs instruments) + OTLP collector wiring.
- Observability-driven issue loop (alert → issue).
- Optional: `LICENSE`, `CONTRIBUTING`, web-session `SessionStart` setup hook.
