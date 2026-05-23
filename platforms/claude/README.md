# Claude Engine

`iops_claude` is a fully self-contained reference engine (strict isolation,
D-0011) that implements the [engine-adapter contract](../../framework/engines/ENGINE-ADAPTER-CONTRACT.md).
It imports only the `framework/` spec — never another engine. Its validation
logic is an independent implementation, kept identical to other engines by the
golden conformance vectors (D-0012).

Claude models a **Claude Code execution engine**: it implements the
[AGENT_UPDATE_PROTOCOL](../../framework/execution/AGENT_UPDATE_PROTOCOL.md)
(`start_session` → `acquire_lease` → `record_touched_file` → `record_evidence`
→ `reconcile`), recording ledger transactions from observed local edits.

## Hook-guardrail expectations

Per [HOOK_INTEGRATION_POINTS](../../framework/execution/HOOK_INTEGRATION_POINTS.md):

- Hooks may **append** to and **read** the ledger — never mutate prior entries.
- The `pre_complete` hook is the only veto point, and only by failing the gate.
- Edits outside `isolation_scope.allowed_roots`, or across client/project
  boundaries, are rejected.

Slice 1 exercises the protocol methods programmatically; live Claude Code hook
wiring is a follow-up.

## Use

```bash
pip install -e ".[dev]"
iops-claude ledger validate path/to/ledger.yaml
iops-claude gate run path/to/ledger.yaml path/to/gate.yaml
iops-claude audit report baseline.yaml comparison.yaml
iops-claude monitor validate manifest.yaml
```

OpenTelemetry is an optional extra (`pip install -e ".[otel]"`); without it a
no-op monitoring provider is used.
