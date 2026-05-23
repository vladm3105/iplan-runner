# Session Handoff

> Sessions run in ephemeral containers. **Only committed + pushed work
> survives.** Keep this file current before stopping or switching context.

## Current state - 2026-05-23

- Branch: `claude/iplan-execution-framework-jc03k`
- Phase: **Planning** (SDD workflow: plan → ≥2 review → implement → verify → land).
- Repo decisions captured in `plans/DECISIONS.md` (D-0001..D-0010).
- `plans/PLAN-001_iplan-execution-ledger-runtime.md` drafted and hardened with
  two review passes. **Status: IN REVIEW — awaiting user approval before
  implementation.**

## What PLAN-001 will build (slice 1)

Hybrid spec + runtime: engine-agnostic contract in `framework/` (execution
ledger / verify-gate / chain / audit + OTel monitoring + engine-adapter), a
shared `core/` (`iops_core`) runtime, and **two full engines**
(`platforms/hermes`, `platforms/claude`), with a conformance suite.

## Next action

- Await approval / feedback on `PLAN-001`.
- On approval: implement Tasks 1→9 in order, committing per task, running
  conformance + `pytest` + `ruff` + `mypy --strict` before "done".

## Backlog (post slice 1)

- `platforms/codex/`, `platforms/vertexai/` engines (own plans).
- Live Claude Code hook wiring for the `claude` engine.
- Observability-driven issue loop (OTLP collector + alert→issue).
- Optional: `LICENSE`, CI workflow, web-session `SessionStart` setup hook.
