# Framework Contract

This directory is the **engine-agnostic contract**. It contains **no code** —
only the portable specification that every engine in `platforms/` implements.

## The execution-control model

> **IPLAN** (plan, from SDD) → **Ledger** (append-only execution evidence) →
> **Gate** (independent completion proof) → **Monitor** (post-implementation
> observation).

## Contents

| Path | Purpose |
|------|---------|
| `VERSION` | The single spec-version source. The registry and every engine's `FRAMEWORK_SPEC_VERSION` must equal it. |
| `registry/EXECUTION_REGISTRY.yaml` | Single source of truth: artifacts, engines, coarse error codes, rule-catalog + vectors references. |
| `execution/` | Ledger, verify-gate, chain-ledger, audit-report templates + the agent-update / hook-integration / saga / isolation protocol docs. |
| `monitoring/` | OpenTelemetry-aligned post-implementation monitoring manifest + docs. |
| `engines/ENGINE-ADAPTER-CONTRACT.md` | The interface every engine implements, including the `validate(document)` parity entry point. |
| `conformance/rule-ids.yaml` | Canonical fine-grained rule-ID catalog (the unit of behavioral parity). |
| `conformance/RULE-IDS.md` | Human-readable rule catalog. |
| `conformance/vectors/` | Golden input documents + expected outcomes, replayed against every engine. |

## How parity works

Engines duplicate logic (strict isolation, D-0011). They are kept behaviorally
identical by **data, not shared code** (D-0012): every validator emits stable
`rule_id`s from `conformance/rule-ids.yaml`, and `tests/conformance/` replays
the golden vectors against each engine asserting the rule-ID set + status match.
Human-readable messages may differ between engines and are never compared.
