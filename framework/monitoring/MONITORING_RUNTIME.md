# Monitoring Runtime

How the post-implementation monitoring contract (`MONITORING-MANIFEST-TEMPLATE`)
is *run*: SLO evaluation → alert evaluation → issue record, a probe server, and
the distinction between **product monitoring** and **engine self-telemetry**.

## SLO evaluation

`evaluate_slos(manifest, samples)` (PLAN-001) compares collected `samples` (keyed
by metric name) against each SLO's `objective`, resolved via the SLO's
`signal_ref`. Baseline semantics: `met = value >= objective` (direction-aware
SLOs are future work). An SLO is **breached** when `met is False`.

## Alert evaluation (SLO-breach-driven)

```
evaluate_alerts(manifest, samples) -> [{alert_id, slo_ref, severity, escalation_owner}]
```

Each `alert_rules[]` entry carries a `slo_ref`; the alert **fires** iff that SLO
is breached. An `alert_rule` whose `slo_ref` does not resolve to a declared SLO
yields nothing. The rule's `when` string is **human-readable documentation** — it
is **not** evaluated (no arbitrary-expression eval). Deterministic + pure.

## Issue record

```
build_issue(alert, manifest) -> {title, body, source_iplan, source_ledger, severity, escalation_owner}
```

A tracker-ready record bound to the manifest's `@iplan` / `@ledger` identity.
PLAN-010 produces the **record**; *posting* it to a tracker (GitHub Issues) is
the post-`v1.0` observability-driven issue loop.

## Probe server

`probe_server(manifest, health)` serves the manifest's `probes` paths
(`/healthz`, `/readyz`, `/startupz`) over HTTP, each returning `200` + a JSON
status from an injected `health()` callable (default healthy). It is real I/O
(binds a socket) — tested per engine on an ephemeral port, not in conformance.

## Live OpenTelemetry

The OTel provider emits spans (PLAN-001) and — from this phase — metrics + logs,
behind the optional `[otel]` extra (imported lazily). Absent the extra, the
**no-op provider is the default**, so the contract, alert evaluation, and tests
run offline; a live OTLP collector is operator configuration.

## Product monitoring vs engine self-telemetry

Two distinct scopes, deliberately separated:

- **Product monitoring** — the manifest: SLOs/alerts of the *shipped product*.
- **Engine self-telemetry** — `emit_run_telemetry(provider, ledger)` records the
  *run's own* signals (task counts, completed/blocked, durations) via the
  monitoring provider. It observes the engine, not the product.

Monitoring is **observe-only**: it reads ledger/sample state and never changes
the run loop.
