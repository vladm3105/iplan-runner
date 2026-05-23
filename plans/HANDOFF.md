# Session Handoff

> Sessions run in ephemeral containers. **Only committed + pushed work
> survives.** Keep this file current before stopping or switching context.

## Current state - 2026-05-23

- Branch: `claude/iplan-execution-framework-jc03k`
- Phase: **PLAN-001 implemented** (SDD workflow: plan → 4 review passes →
  implement → verify → land).
- Repo decisions captured in `plans/DECISIONS.md` (D-0001..D-0012; D-0007
  superseded by D-0011).
- `plans/PLAN-001_iplan-execution-ledger-runtime.md` — **DONE**.

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
