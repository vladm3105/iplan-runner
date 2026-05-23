# Session Handoff

> Sessions run in ephemeral containers. **Only committed + pushed work
> survives.** Keep this file current before stopping or switching context.

## Current state - 2026-05-23

- Branch: `claude/iplan-execution-framework-jc03k`
- Phase: **Planning** (SDD workflow: plan → ≥2 review → implement → verify → land).
- Repo decisions captured in `plans/DECISIONS.md` (D-0001..D-0012; D-0007
  superseded by D-0011).
- `plans/PLAN-001_iplan-execution-ledger-runtime.md` drafted, reworked for
  **strict isolation + golden vectors**, and hardened across four review passes.
  **Status: IN REVIEW — awaiting user approval before implementation.**

## What PLAN-001 will build (slice 1)

Hybrid spec + runtime with **strict engine isolation** (D-0011): engine-agnostic
contract in `framework/` (execution ledger / verify-gate / chain / audit + OTel
monitoring + engine-adapter + **rule-ID catalog + golden vectors**), and **two
fully self-contained engines** (`platforms/hermes`, `platforms/claude`) that
share no code. Behavioral parity is enforced by replaying golden vectors against
each engine + a cross-engine differential test (D-0012).

## Next action

- Await approval / feedback on `PLAN-001`.
- On approval: implement Tasks 1→9 in order, committing per task, running
  conformance + `pytest` + `ruff` + `mypy --strict` before "done".

## Backlog (post slice 1)

- `platforms/codex/`, `platforms/vertexai/` engines (own plans).
- Live Claude Code hook wiring for the `claude` engine.
- Observability-driven issue loop (OTLP collector + alert→issue).
- Optional: `LICENSE`, CI workflow, web-session `SessionStart` setup hook.
