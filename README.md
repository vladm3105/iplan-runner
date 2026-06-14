# iplan-runner — OSS IPLAN executor

`iplan-runner` is the **execution / operations plane** companion to
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

## Capabilities (v1.0.0)

The full pipeline — **IPLAN intake → run loop → gate → land → handover →
monitor** — works end-to-end on both engines (see
[`examples/`](examples/README.md) and the per-engine acceptance test):

- **Intake** an approved SDD-IPLAN into an isolation-scoped manifest.
- **Run** tasks with a pluggable executor (mock / scripted / live), a durable
  hash-chained ledger, saga retry / compensation / idempotency, and leases.
- **Effect** sandboxed writes + commands (lexical + realpath jail) with evidence
  capture and secret redaction.
- **Gate** completion independently; **land** a green, reconciled run as a git
  commit; emit a **handover** receipt.
- **Secure**: HMAC-signed ledger (`verify_ledger`), role-based `authorize`,
  agent-first auth direction (D-0015).
- **Operate**: pause / abort / resume / resolve blockers (HITL); config +
  secrets from the environment; resource budgets.
- **Monitor**: SLO/alert evaluation, probes, optional OpenTelemetry, engine
  self-telemetry. **Chain** multiple IPLANs with `run_chain`.

Start with [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).

## Status & stability

From **`v1.0.0`** the `framework/` **contract is stable under SemVer**: additive
changes are minor; a breaking contract change bumps the major version. The
conformance suite is the gate — `framework/VERSION` is the single source of
truth, and the registry + every engine's `FRAMEWORK_SPEC_VERSION` must equal it.
Runtime internals may still evolve within the contract.

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
| `examples/` | Runnable end-to-end worked example |
| `docs/` | Getting-started guide + security review |
| `plans/` | Development plans + decisions |

See `CLAUDE.md` for the development workflow, [`CONTRIBUTING.md`](CONTRIBUTING.md)
for how to contribute, and `plans/DECISIONS.md` for architecture rationale.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
