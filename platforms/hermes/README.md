# Hermes Engine

`iplan_hermes` is a fully self-contained reference engine (strict isolation,
D-0011) that implements the [engine-adapter contract](../../framework/engines/ENGINE-ADAPTER-CONTRACT.md).
It imports only the `framework/` spec — never another engine.

Hermes models an **MCP-server engine**: it exposes the execution contract as
tool functions (`iops_validate_ledger`, `iops_run_gate`, `iops_audit_report`,
`iops_monitor_check`) and dispatches execution through an API executor
(`run_executor`).

## Ledger-verification expectations

- A ledger does **not** self-attest completion; `run_gate` is the authority.
- Completed tasks must carry evidence and passing acceptance.
- Every execution-log event is hash-chained and isolation-scoped; a path outside
  `allowed_roots` or a scope mismatch fails the gate.
- All validation findings are emitted as catalog rule IDs
  (`framework/conformance/rule-ids.yaml`); behavior is pinned by the golden
  vectors.

## Use

```bash
pip install -e ".[dev]"
iplan-hermes ledger validate path/to/ledger.yaml
iplan-hermes gate run path/to/ledger.yaml path/to/gate.yaml
iplan-hermes audit report baseline.yaml comparison.yaml
iplan-hermes monitor validate manifest.yaml
iplan-hermes monitor slo-check manifest.yaml samples.yaml
```

OpenTelemetry is an optional extra (`pip install -e ".[otel]"`); without it a
no-op monitoring provider is used.
