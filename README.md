# AI Doc Flow — IOps Framework

`aidoc-flow-iops-framework` is the **execution / operations plane** companion to
[SDD](https://github.com/vladm3105/aidoc-flow-framework) (the control plane). It
turns an **approved IPLAN** into auditable execution.

## The model

```
SDD control plane            │  IOps execution plane (this repo)
BRD → PRD → … → IPLAN         │  IPLAN ─▶ Ledger ─▶ Gate ─▶ Monitor
"done when committed+green"   │  plan    evidence   proof    observe
                              │  (from   (append-   (indep.  (OTel,
                              │   SDD)    only,      completion SLOs)
                              │           hashed)    check)
```

- **Ledger** — an append-only, hash-chained, isolation-scoped record of what
  agents actually did (tasks, leases, evidence, blockers, reconciliation).
- **Gate** — independent verification that a completion claim is valid.
- **Monitor** — post-implementation OpenTelemetry signals + SLOs, bound to the
  same IPLAN/ledger identity.

A ledger binds to its source IPLAN by `id` + `version` + `checksum`. This repo
takes **no dependency on**, and never modifies, the SDD repo.

## Hybrid: contract + runtimes

- `framework/` — the engine-agnostic **contract** (YAML + Markdown, no code):
  execution templates, monitoring manifest, the engine-adapter contract, the
  registry, a fine-grained **rule-ID catalog**, and **golden conformance
  vectors** that pin validation *behavior*.
- `platforms/<engine>/` — fully self-contained reference **runtimes**. Slice 1
  ships `hermes` (MCP-server engine) and `claude` (Claude Code engine). They
  share **no code** (strict isolation); golden vectors keep their verdicts
  identical.
- `tests/conformance/` — replays the vectors against every engine and enforces
  isolation + spec parity.

## Repo map

| Path | What |
|------|------|
| `framework/execution/` | Ledger / verify-gate / chain / audit templates + protocol docs |
| `framework/monitoring/` | OTel-aligned post-implementation monitoring contract |
| `framework/engines/` | Engine-adapter contract |
| `framework/registry/` | Single source of truth for contract artifacts |
| `framework/conformance/` | Rule-ID catalog + golden vectors |
| `platforms/hermes/`, `platforms/claude/` | Reference engines |
| `tests/conformance/` | Vector replay + isolation + parity |
| `plans/` | Development plans + decisions |

See `CLAUDE.md` for the development workflow and `plans/DECISIONS.md` for
architecture rationale.
