# Chain Model

How a **chain** of IPLANs is executed. The chain-ledger *contract* (validation,
`CHAIN.*`) is PLAN-001; this is the *runtime* that drives a chain by composing the
single-IPLAN run loop (`RUN_MODEL`).

## Chain order

```
chain_order(iplan_chain) -> [iplan_id]
```

A stable topological order over `depends_on`, tie-broken by `(order, iplan_id)`
among ready nodes — deterministic across engines. Cyclic remnants fall back to
the smallest `(order, iplan_id)`.

## Execution

`run_chain(chain, iplans, executor_for, *, clock, ids, sleep, control)`:

1. Compute `chain_order`.
2. For each IPLAN in order:
   - **Control checkpoint** (between IPLANs): `aborted`/`paused` stops the chain.
   - **Upstream gating**: if any `depends_on` upstream is **not reconciled**, the
     IPLAN is **not run**; its node stays `reconciled: false`.
   - Otherwise run it via the single-IPLAN loop:
     `run(iplans[iplan_id], executor_for(iplan_id), clock=…, ids=…, sleep=…)`.
     The node's `reconciled` = the sub-ledger's `reconciliation.allowed`.
3. Build the chain ledger; `chain_reconciliation.allowed` iff **every** node
   reconciled.

One injected `clock`/`ids` threads the whole chain, so sub-ledgers and the chain
ledger are deterministic (independent engines produce identical results).

## Cross-plan leases

`cross_plan_leases` declare per-IPLAN resource holds. Execution is **sequential**
(single-process), so a resource is free before the next IPLAN runs — no
contention. Overlapping *unreleased* declarations are a validation error
(`CHAIN.LEASE_OVERLAP`); the runtime does not create them. Distributed /
concurrent lease coordination is post-`v1.0`.

## Chain ledger (output)

`build_chain_ledger` produces an `iplan-chain-ledger`:

- `chain_control` (`chain_id`, `status`),
- `iplan_chain` (each node + its `reconciled` flag),
- `execution_tiers`, `cross_plan_leases` (carried through),
- `chain_reconciliation` (`allowed`).

It is **identity-free** — it references IPLANs by id + records reconciled flags;
it does **not** embed the sub-ledgers (which carry per-engine `agent_id`). The
sub-ledgers are returned separately (`ChainResult.sub_ledgers`). A fully
reconciled chain ledger validates clean under `CHAIN.*`; an upstream-blocked one
correctly reports `CHAIN.UPSTREAM_UNRECONCILED` + `allowed: false` (a truthful
incomplete state).
