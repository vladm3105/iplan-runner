# Engine Adapter Contract

Every engine in `platforms/` implements this interface. Engines are **fully
self-contained** (strict isolation, D-0011): an engine imports only the
`framework/` spec — never another engine. Behavioral parity is proven by golden
vectors (D-0012), not shared code.

## Interface

```python
class EngineAdapter(Protocol):
    def engine_id(self) -> str:
        """Stable lowercase engine identifier, e.g. "hermes"."""

    def capabilities(self) -> dict:
        """Declared capabilities, e.g. {"validate": True, "gate": True,
        "monitor": True, "executor": "api"|"hooks"|None}."""

    def validate(self, document: dict) -> dict:
        """THE parity entry point. Dispatch on metadata.document_type and run the
        matching validator. Returns:

            {
              "status": "pass" | "warn" | "fail",
              "findings": [
                {"rule_id": str, "severity": "error"|"warning", "message": str},
                ...
              ],
            }

        status is "fail" if any finding is an error, "warn" if only warnings,
        else "pass". rule_id values come from framework/conformance/rule-ids.yaml.
        """

    def run_gate(self, ledger: dict, gate: dict) -> dict:
        """Evaluate a verification-gate document against a ledger, mapping each
        GATE-LEDGER-NNN rule to its validator rule IDs. Returns per-rule results
        plus an overall {"status": "passed"|"failed"}."""

    def record_transaction(self, ledger: dict, txn: dict) -> dict:
        """Append a saga transaction + execution_log event (hash-chained).
        Returns the updated ledger. Append-only."""

    def emit_execution_log(self, event: dict) -> None:
        """Emit a structured execution-log event (and an OTel log if wired)."""

    def instrument(self, manifest: dict) -> None:
        """Wire monitoring from a monitoring manifest. Sets the OTel Resource
        service.name to the engine (e.g. "iops-hermes") then configures signals.
        A no-op MonitoringProvider is used when the [otel] extra is absent."""
```

## Parity rules

- `validate` outcomes are compared across engines by **rule-ID set + status**
  only. Human-readable `message` text **may differ** between engines and is
  never compared.
- Each emitted finding's `severity` must equal the catalog severity for its
  `rule_id`.
- Dispatch by `metadata.document_type`:
  `iplan-ledger` → ledger validator, `iplan-chain-ledger` → chain validator,
  `iplan-audit-report` → audit validator,
  `iplan-monitoring-manifest` → monitoring validator.

## Isolation rule

An engine package (`iops_<engine>`) must not import any other engine package.
Enforced by `tests/conformance/test_engines.py`.
