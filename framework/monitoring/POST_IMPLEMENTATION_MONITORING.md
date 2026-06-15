# Post-Implementation Monitoring

Once an IPLAN ships, monitoring observes the running result. The monitoring
manifest binds observation to the **same `@iplan` / `@ledger` identity** that
governed execution, so every signal is traceable back to the plan that produced
it (D-0006).

## Model

```
Ledger (what was done) ──▶ Monitoring Manifest ──▶ OTel signals ──▶ SLO eval ──▶ alerts
        @iplan/@ledger identity carried through as span/metric attributes
```

## OpenTelemetry mapping

Monitoring is OpenTelemetry-based and exporter-agnostic:

- **Traces** — spans for execution/runtime activity, attributed with
  `iplan.id`, `ledger.id`, `task.id`, `client.id`, `project.id`.
- **Metrics** — instruments (gauge / counter / histogram) that SLOs reference by
  name via `signal_ref`.
- **Logs** — structured execution events.

Engines wire the OTel SDK behind an optional `[otel]` extra and export via OTLP;
the OTLP endpoint is operator configuration. Absent the extra, a console/no-op
provider is used so the contract and SLO evaluation still run offline.

## SLO evaluation

`evaluate_slos(manifest, samples)` compares collected sample values against each
SLO's `objective` over its `window`. It is exporter-independent: samples are
supplied as data, so SLO logic is testable without a live backend. An SLO whose
`signal_ref` does not resolve to a declared metric is `MON.SIGNAL_REF_UNRESOLVED`.

## Monitoring window

`monitor_control.monitoring_window` defines the post-implementation observation
period (`starts_at` + ISO-8601 `duration`). Alerts that breach during the window
escalate to `alert_rules[].escalation_owner`, feeding a future
observability-driven issue loop.

## Validation

| Rule | Meaning |
|------|---------|
| `MON.SOURCE_BINDING_MISSING` | `source_iplan` or `source_ledger` absent |
| `MON.SLO_MISSING_TARGET` | an SLO has no `objective` |
| `MON.SIGNAL_REF_UNRESOLVED` | an SLO `signal_ref` is not a declared metric |
| `MON.PROBE_MISSING` | a health / readiness / startup probe is absent (warning) |
