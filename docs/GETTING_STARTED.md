# Getting started

This guide ties the framework's phases together into one run. For a complete,
runnable artifact see [`examples/`](../examples/README.md); for the asserted
version see `platforms/<engine>/tests/test_acceptance.py`.

## Install

Each engine is a self-contained package (strict isolation — they share no code):

```bash
pip install -e "./platforms/hermes[dev]"   # and/or
pip install -e "./platforms/claude[dev]"
```

The CLIs are `iplan-hermes` and `iplan-claude`; the Python API is `HermesEngine` /
`ClaudeEngine`. They are interchangeable — golden vectors keep their verdicts
identical.

## The pipeline

> **IPLAN** (intake) → **Ledger** (run) → **Gate** (proof) → **Land** (commit) →
> **Handover** → **Monitor**.

```python
from iplan_hermes import HermesEngine
from iplan_hermes.executor.base import IdSource

engine = HermesEngine()

# 1. Intake — normalize an approved SDD-IPLAN into an iplan-intake manifest.
manifest = engine.ingest_iplan("examples/IPLAN-EXAMPLE.yaml")
assert engine.validate(manifest)["status"] == "pass"

# 2. Run — execute tasks; the ScriptedExecutor performs real edits + checks.
import yaml
actions = yaml.safe_load(open("examples/actions.yaml").read())
result = engine.run(manifest, engine.scripted_executor(actions, workspace),
                    clock=clock, ids=IdSource())
assert result.gate_result["status"] == "passed"          # green
assert result.ledger["reconciliation"]["allowed"]        # reconciled

# 3. Land — commit the green, reconciled run to a branch (operator-authorized).
landed = engine.land(result.ledger, workspace, branch="iops/run",
                     actor={"id": "op", "role": "operator"})

# 4. Handover — a receipt: completed, with the commit recorded.
receipt = engine.build_handover(landed.ledger, landed.gate_result)

# 5. Monitor — evaluate SLOs/alerts against collected samples.
mon = yaml.safe_load(open("examples/monitoring.yaml").read())
alerts = engine.evaluate_alerts(mon, {"availability_ratio": 99.95})  # [] when healthy
```

### Signing

Set a signing key (from the environment / `Config.signing_key`) and `land`
stamps every execution-log event with an HMAC signature; `verify_ledger`
re-verifies the chain and every signature:

```python
engine._config.signing_key = "your-key"   # secrets come from env in practice
landed = engine.land(result.ledger, workspace, branch="iops/run")
assert engine.verify_ledger(landed.ledger) is True
```

## Capabilities by phase

| Phase | Capability | Entry point |
|-------|------------|-------------|
| Intake | normalize SDD-IPLAN → manifest | `ingest_iplan`, `validate` |
| Run loop | orchestrate tasks, ledger, gate | `run`, `run_gate` |
| Effectors | sandboxed writes + commands, evidence | `scripted_executor`, `classify_path` |
| Saga / leases | retry / compensation / idempotency, lease lifecycle | inside `run` (`max_retries`) |
| Landing | commit a green run to git | `land` |
| Security | HMAC signing, role-based authz | `sign_ledger` / `verify_ledger`, `authorize` |
| Config / budget | env secrets, resource governance | `load_config`, `Budget` / `check` |
| HITL control | pause / abort / resume / resolve | `pause`, `abort`, `resume`, `resolve_blocker` |
| Monitoring | SLO/alert eval, probes, OTel, self-telemetry | `evaluate_alerts`, `build_issue` |
| Chain | multi-IPLAN orchestration | `run_chain` |

## CLI

See the [worked-example walkthrough](../examples/README.md) for the
`intake` / `run --land` / `monitor` / `status` commands.

## Verify

```bash
python -m unittest discover -s tests/conformance -v   # vectors + isolation + parity
pytest platforms/hermes platforms/claude -q           # engine + acceptance tests
ruff check platforms && mypy --strict platforms/hermes/src platforms/claude/src
```

## Where to look next

- [`examples/`](../examples/README.md) — the runnable end-to-end example.
- [`SECURITY.md`](../SECURITY.md) + [`docs/SECURITY_REVIEW.md`](SECURITY_REVIEW.md) — trust boundary + threat model.
- `CLAUDE.md` — development workflow; `plans/DECISIONS.md` — architecture rationale.
