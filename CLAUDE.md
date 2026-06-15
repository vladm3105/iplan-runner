# CLAUDE.md

Guidance for working in `iplan-runner`.

## What this repo is

The **execution / operations plane** that picks up where SDD
(`aidoc-flow-framework`, the control plane) stops. SDD owns BRD → … → IPLAN
("done when committed + green"). This framework consumes an **approved** IPLAN
at SDD's `EXEC-Ready (≥90)` boundary and runs the loop:

> **IPLAN** (plan, from SDD) → **Ledger** (append-only execution evidence) →
> **Gate** (independent completion proof) → **Monitor** (post-implementation
> observation).

See `plans/DECISIONS.md` for the architecture decisions (D-0001..D-0012).

## Layout

- `framework/` — engine-agnostic **contract** (spec only, no code): execution
  templates, monitoring manifest, engine-adapter contract, registry, the
  rule-ID catalog, and the golden conformance vectors.
- `platforms/<engine>/` — fully self-contained reference **runtimes**
  (`hermes`, `claude`, …). Each is a complete implementation.
- `tests/conformance/` — replays the golden vectors against every engine and
  enforces isolation + spec parity.
- `plans/` — development plans (start from `plans/PLAN-TEMPLATE.md`).

## Development workflow

**plan → review (≥2 passes) → implement → verify → land.**

1. Plan into `plans/` before touching code. A plan needs ≥2 review passes
   recorded in its `## Review log` before implementation. **Size the plan to
   the problem:** ~N fixes for N discovered issues, not N speculative features.
   If a review pass surfaces more gaps than the original problem had, the
   surplus is speculative scope — cut it.
2. Implement one task per commit (conventional prefix: `feat`/`fix`/`test`/
   `docs`/`chore`/`refactor`).
3. Verify before calling anything done (see below).
4. **Update docs with code.** Any PR that touches `framework/` or
   `platforms/<engine>/src/` (or an engine's `pyproject.toml` /
   `FRAMEWORK_SPEC_VERSION`) must update `CHANGELOG.md` in the same PR —
   an `[Unreleased]` entry is enough; a release header on a version cut. Also
   update `plans/HANDOFF.md`, `TODO.md`, `ROADMAP.md`, `README.md`, and
   `docs/**` as their content is affected. CI gates the `CHANGELOG.md`
   requirement (`.github/workflows/docs-gate.yml` → `tests/chg/docs_gate.py`);
   include `[no-changelog]` in a commit message when the change is genuinely
   not user-facing (internal refactor, pure test, CI-only).
5. Update `plans/HANDOFF.md` before stopping — **only committed + pushed work
   survives** the ephemeral container.

## Durable conventions

- **The spec is the contract.** `framework/` holds no code.
- **Strict engine isolation (D-0011).** Each engine imports only the
  `framework/` spec — **never** another engine's package. Code duplication
  across engines is intentional.
- **Parity is proven by golden vectors (D-0012),** not shared code. Validators
  emit fine-grained `rule_id`s from `framework/conformance/rule-ids.yaml`;
  conformance compares the rule-ID set + status, never message text.
- **Single source of truth** for contract artifacts is
  `framework/registry/EXECUTION_REGISTRY.yaml`.
- **Never weaken a conformance check to make it pass.** Fix the engine.
- `framework/VERSION` is the single spec-version source; the registry and every
  engine's `FRAMEWORK_SPEC_VERSION` must equal it.

## Per-repo governance — this repo owns its own continuity

The `aidoc-flow` workspace is **multi-repo**. Each repo governs its own
activity tracking; cross-session continuity is per-repo. The durable
surfaces for **this** repo:

| Surface | Path (in this repo) |
|---|---|
| Live HANDOFF | `plans/HANDOFF.md` |
| TODO / backlog | `TODO.md` (root) |
| Decisions log | `plans/DECISIONS.md` (D-0001..) |
| Plans | `plans/PLAN-NNN_*.md` |
| Roadmap | `ROADMAP.md` |

**Never put any of these in `tmp/`** — `tmp/` is for transient working
files; nothing in it survives a context-clear or new session.
**Never centralize in the umbrella `aidoc-flow/`** — the umbrella holds
no dev; plans, decisions, and tracking live in the owning submodule.

A future session entered through **this** repo must find that repo's
state here. Cross-repo coordination (e.g., a framework-spec change
that this engine implements) references the sibling `framework/` repo
by path; iplan-runner's own state never relocates into the framework.

## Verify

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```
