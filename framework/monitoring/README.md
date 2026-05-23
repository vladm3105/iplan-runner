# Monitoring Contract

OpenTelemetry-aligned post-implementation monitoring, bound to the IPLAN/ledger
identity it observes.

| File | Purpose |
|------|---------|
| `MONITORING-MANIFEST-TEMPLATE.yaml` | The manifest: SLOs, OTel signals, probes, alert rules (`iplan-monitoring-manifest`, validated under `MON-001`) |
| `POST_IMPLEMENTATION_MONITORING.md` | The monitoring model, OTel mapping, SLO evaluation, and window semantics |

See `framework/conformance/rule-ids.yaml` for the `MON.*` validation rules.
