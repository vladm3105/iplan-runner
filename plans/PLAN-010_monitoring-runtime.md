# Monitoring Runtime Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** Make post-implementation monitoring *run* (Roadmap Phase 10 →
`v0.10.0`): a **probe HTTP server** (`/healthz` `/readyz` `/startupz`), **live
OTel** metrics/logs (today no-ops), **alert evaluation → issue record**, and a
clear split between **product monitoring** (the manifest) and **engine
self-telemetry** (the run itself).

**Architecture:** Additive (D-0014). New `framework/monitoring/MONITORING_RUNTIME.md`
+ an `alert/` conformance kind. Two regimes (as PLAN-008): the engine-agnostic
**alert evaluation** + **issue record** are pure → golden-vector'd + differential;
the **probe server** and **live OTel** are real I/O → per-engine / integration
(behind the `[otel]` extra, skipped offline; the no-op provider stays the
default). The run loop is untouched — monitoring is observe-only.

**Tech Stack:** Python ≥3.11 (`http.server`); optional `[otel]`; `pytest`;
`unittest` conformance; `ruff` + `mypy --strict`; YAML.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-010 |
| Depends on | `PLAN-001`..`PLAN-009` (DONE); D-0011..D-0015; Roadmap Phase 10 |
| Status     | DONE - 2026-05-24 |
| Feeds      | GA (`v1.0.0`); the post-v1.0 observability-driven issue loop |

## Objective

PLAN-001 shipped the monitoring *contract* (manifest + `MON-001`); the runtime is
no-ops. PLAN-010 makes it real:

1. **Alert evaluation.** `evaluate_alerts(manifest, samples) -> [alerts]` — an
   alert rule fires when its referenced SLO is breached (no arbitrary-expression
   eval). Pure, deterministic.
2. **Issue record.** `build_issue(alert, manifest) -> issue` — a tracker-ready
   record bound to the same `@iplan` / `@ledger` identity (the *record*; posting
   it is the post-v1.0 loop).
3. **Probe server.** `probe_server(manifest, health)` serving the manifest's
   probe paths with a JSON status.
4. **Live OTel.** Extend the OTel provider to emit metrics + logs (not just
   spans), behind `[otel]`; the no-op provider stays the offline default.
5. **Self-telemetry.** `emit_run_telemetry(provider, ledger)` records the run's
   own signals (task counts, blocked/completed) — distinct from product SLOs.

## Scope

**In:**

1. `framework/monitoring/MONITORING_RUNTIME.md` — alert evaluation
   (SLO-breach-driven, via `alert_rules[].slo_ref`), issue-record shape, probe
   server, self-telemetry vs product distinction, live-OTel note. Add `slo_ref`
   to `alert_rules` in the manifest template. Registry → doc + `alert_root`.
2. Golden vectors: `framework/conformance/alert/<name>` (`{manifest, samples}` →
   `{alerts}`).
3. Engine-agnostic (copied identically, parity-pinned): `monitoring/alerts.py`
   (`evaluate_alerts`, `build_issue`).
4. Per engine: `monitoring/probes.py` (`probe_server`); extend `monitoring/otel.py`
   (live metrics/logs behind `[otel]`); `monitoring/telemetry.py`
   (`emit_run_telemetry`); engine methods (`evaluate_alerts`, `build_issue`,
   `serve_probes`, `instrument`/self-telemetry); tests.
5. Conformance: `tests/conformance/test_alerts.py` (cross-engine alert parity);
   registry path check. Probe server + OTel are per-engine / integration.
6. Spec bump to `0.10.0`.

**Out:**

1. **Posting issues** to GitHub/a tracker — that is the post-v1.0
   observability-driven issue loop; here we build the issue *record*.
2. **Running a live OTLP collector** — real OTel is integration-only behind the
   extra (skipped offline); the no-op provider is the default.
3. **Arbitrary `when` expression evaluation** — alerts fire on a referenced SLO
   breach (`slo_ref`); `when` stays human-readable.
4. **Direction-aware SLOs** — `met = value >= objective` baseline (PLAN-001);
   richer SLO semantics are future work (documented).
5. Run-loop changes — monitoring is observe-only.

## Approach

**Alerts are SLO-breach-driven (no eval).** `evaluate_alerts(manifest, samples)`
runs `evaluate_slos` (samples keyed by metric name → each SLO's `signal_ref`),
then for each `alert_rule` with a `slo_ref` whose SLO is breached (`met is
False`), emits `{alert_id, slo_ref, severity, escalation_owner}`. An `alert_rule`
whose `slo_ref` doesn't resolve to an SLO yields nothing. This avoids evaluating
arbitrary `when` strings (the `when` becomes human-readable documentation). Pure
+ deterministic → golden-vector'd + differential. `build_issue` is also pure and
unit-tested per engine.

**Issue record, not delivery.** `build_issue(alert, manifest)` returns a
tracker-ready dict (`title`, `body`, `source_iplan`, `source_ledger`, `severity`,
`escalation_owner`) bound to the manifest's `@iplan`/`@ledger`. Pure. *Posting*
it (GitHub Issues) is the post-v1.0 loop — out of scope.

**Probe server is real I/O → per-engine.** `probe_server(manifest, health)`
starts a stdlib `http.server` serving the manifest's `probes` paths; each returns
`200` + a JSON status from an injected `health()` callable (default healthy).
Tested per-engine on an ephemeral port; not conformance (binds a socket).

**Live OTel behind the extra.** The OTel provider (PLAN-001 spans-only) gains
real `record_metric` / `log`; imported lazily (importlib), so the base build +
`mypy --strict` are unaffected and the **no-op provider stays the default**
offline. Exercised by an integration test skipped when `[otel]` is absent.

**Two telemetry scopes, kept distinct.** *Product monitoring* = the manifest
(SLOs of the shipped product). *Engine self-telemetry* = `emit_run_telemetry(
provider, ledger)` recording the run's own signals (task counts, completed /
blocked, durations). Documented so they aren't conflated.

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/monitoring/MONITORING_RUNTIME.md` | Alert eval, issue record, probe server, self-telemetry vs product, live OTel. |
| `framework/monitoring/MONITORING-MANIFEST-TEMPLATE.yaml` | + `alert_rules[].slo_ref`. |
| `framework/conformance/alert/<name>/{input,expect}.yaml` | `{manifest, samples}` → `{alerts}`. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + the doc, `alert_root`. |
| `platforms/<engine>/src/iops_<engine>/monitoring/alerts.py` | `evaluate_alerts`, `build_issue` (engine-agnostic). |
| `platforms/<engine>/src/iops_<engine>/monitoring/probes.py` | `probe_server(manifest, health)`. |
| `platforms/<engine>/src/iops_<engine>/monitoring/otel.py` | live metrics/logs behind `[otel]`. |
| `platforms/<engine>/src/iops_<engine>/monitoring/telemetry.py` | `emit_run_telemetry(provider, ledger)`. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | `evaluate_alerts`/`build_issue`/`serve_probes`/self-telemetry. |
| `platforms/<engine>/tests/test_monitoring.py` | alerts, issue record, probe server, self-telemetry; OTel skip-if-absent. |
| `tests/conformance/test_alerts.py` | cross-engine alert-evaluation parity. |

## Step Sequence

### Task 1: Framework monitoring-runtime contract

- [ ] **Step 1:** `MONITORING_RUNTIME.md` — alert evaluation (`slo_ref` breach →
  alert), issue-record shape, probe server, self-telemetry vs product, live-OTel.
- [ ] **Step 2:** add `slo_ref` to `alert_rules` in the manifest template (e.g.
  `ALERT-001` → `slo_ref: SLO-001`).
- [ ] **Step 3:** registry — add the doc + `alert_root: framework/conformance/alert`.
- [ ] **Step 4: parse check + commit** — `feat: add monitoring-runtime contract`.

### Task 2: Alert vectors

- [ ] **Step 1:** `alert/breach` (a manifest + samples where SLO-001 is breached →
  one alert); `alert/healthy` (samples within objective → no alerts);
  `alert/no_ref` (alert_rule without a resolvable `slo_ref` → no alert).
- [ ] **Step 2: commit** — `test: add alert-evaluation vectors`.

### Task 3: Alert evaluation + issue (engine-agnostic, both engines)

- [ ] **Step 1: failing tests** — `evaluate_alerts` over the vectors; `build_issue`
  produces an `@iplan`/`@ledger`-bound record. Fail.
- [ ] **Step 2:** `monitoring/alerts.py` (`evaluate_alerts`, `build_issue`) —
  identical in both engines.
- [ ] **Step 3:** engine methods `evaluate_alerts` / `build_issue`.
- [ ] **Step 4: green** (both) — commit `feat: add alert evaluation + issue record`.

### Task 4: Probe server + live OTel + self-telemetry (per engine)

- [ ] **Step 1: failing tests** — `probe_server` serves `/healthz` etc. (200 +
  JSON) on an ephemeral port; `emit_run_telemetry` records run signals via a
  capturing provider; OTel metrics/logs test (skipped if `[otel]` absent). Fail.
- [ ] **Step 2:** `monitoring/probes.py` — stdlib `http.server` over the manifest
  probes + injected `health`.
- [ ] **Step 3:** extend `monitoring/otel.py` — real `record_metric`/`log` behind
  the lazily-imported SDK; no-op default unchanged.
- [ ] **Step 4:** `monitoring/telemetry.py` — `emit_run_telemetry(provider, ledger)`.
- [ ] **Step 5:** engine `serve_probes` + self-telemetry wiring.
- [ ] **Step 6: green** — `pytest`, `ruff`, `mypy --strict`. Commit
  `feat: add probe server + live otel + self-telemetry to <engine>` (×2,
  independent copies).

### Task 5: Conformance

- [ ] **Step 1:** `test_alerts.py` — cross-engine `evaluate_alerts` parity over
  the alert vectors; extend `test_registry` to `alert_root`.
- [ ] **Step 2: run full suite** + commit `test: add alert conformance`.

### Task 6: Version bump, changelog, handoff

- [ ] **Step 1:** atomic bump to `0.10.0`.
- [ ] **Step 2:** `CHANGELOG.md` `[0.10.0]`; update `HANDOFF.md` + `TODO.md`;
  plan `DONE`.
- [ ] **Step 3: full verification** + commit `chore: release spec v0.10.0
  (monitoring runtime)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green: alert evaluation matches `expect` in each engine + agree;
   all prior checks unchanged at `0.10.0`.
2. Per-engine tests (offline): probe server answers `/healthz` `/readyz`
   `/startupz`; `emit_run_telemetry` records run signals; `build_issue` is
   `@iplan`/`@ledger`-bound; OTel test skips without `[otel]`.
3. `ruff` + `mypy --strict` clean.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Evaluating arbitrary `when` strings is unsafe. | Alerts fire on a referenced SLO breach (`slo_ref`); `when` is human-readable; no eval. |
| R2 | Live OTel needs the SDK / a collector. | Real metrics/logs behind the lazily-imported `[otel]` extra; no-op default; integration test skipped offline (R-pattern from PLAN-008). |
| R3 | Probe server binds a socket → flaky/conformance-unfit. | Per-engine test on an ephemeral port (port 0); not conformance; server is opt-in. |
| R4 | Posting issues implies network/credentials. | Out of scope — we build the issue *record*; delivery is the post-v1.0 loop. |
| R5 | SLO direction (`>=`) is naive → wrong alerts. | Documented baseline; richer direction-aware SLOs are future work; vectors test the wiring, not direction semantics. |
| R6 | Monitoring touches the run loop. | Observe-only: alerts/issue/probes/telemetry read state; the loop is unchanged; prior scenarios byte-identical. |
| R7 | `alert_rules.slo_ref` added to the template breaks parse/contract. | Additive optional field; `test_contract` only checks parse + document_type. |

## Review log

> ≥2 passes before implementation.

### Pass 1 - 2026-05-24

- Finding: evaluating arbitrary `when` expressions is unsafe + non-portable.
  Change: alerts fire on a referenced **SLO breach** via `alert_rules[].slo_ref`;
  `when` is documentation only (R1). Added `slo_ref` to the manifest template.
- Finding: the alert/SLO data flow needed pinning. Clarified: `samples` are keyed
  by metric name; `evaluate_slos` resolves each SLO's `signal_ref`; breach =
  `met is False`; an unresolved `slo_ref` → no alert (the `no_ref` vector).
- Finding: live OTel + probe server can't run in CI. Confirmed two-regime split:
  alert eval (pure) vector'd + differential; OTel behind `[otel]` (skipped
  offline, no-op default), probe server per-engine on an ephemeral port (R2/R3).
- Finding: posting issues implies network/credentials. Confirmed out of scope —
  `build_issue` returns the record; delivery is the post-v1.0 loop (R4).

### Pass 2 - 2026-05-24

- Finding: monitoring must not change run behavior. Confirmed observe-only: alert
  eval / issue / probes / self-telemetry all read state; the run loop and prior
  scenarios are byte-identical (R6).
- Finding: `alert_rules.slo_ref` is additive to the manifest template. Confirmed
  it doesn't affect `test_contract` (parse + document_type) or `MON-001`
  validation (R7).
- Finding: product vs engine telemetry could be conflated. Confirmed kept
  distinct: product = the manifest SLOs; engine = `emit_run_telemetry` over the
  ledger; documented in MONITORING_RUNTIME.
- Verification ↔ surface cross-check: alert evaluation (engine-agnostic) is
  vector'd + differential; probe server / live OTel / self-telemetry are
  per-engine (+ OTel integration skipped offline). No further findings.
