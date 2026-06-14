# Worked example: `IPLAN-EXAMPLE`

A complete run of the execution plane on a tiny IPLAN, end to end:

> **IPLAN** (intake) → **Ledger** (run, real edits) → **Gate** (completion proof)
> → **Land** (commit + sign) → **Handover** → **Monitor**.

Everything here is offline and deterministic — no model API, no network. The
`ScriptedExecutor` performs the *real* file writes and check commands that a
live executor (`ApiExecutor` / `HostRuntimeExecutor`) would otherwise generate.

## Files

| File | What it is |
|------|------------|
| `IPLAN-EXAMPLE.yaml` | An approved SDD-IPLAN (`exec_ready: 95`, 2 tasks, `T2` depends on `T1`). Intake normalizes it into an `iplan-intake` manifest. |
| `actions.yaml` | The action script: per task, the files to write and the check commands to run (list-form, no shell). |
| `monitoring.yaml` | The monitoring manifest bound to the example IPLAN/ledger (SLO + alert rule + probes). |

The two tasks add `src/greeting.py` and `tests/test_greeting.py`; each task's
check imports the result and asserts it behaves.

## Run it with the CLI

Pick an engine — `iplan-hermes` or `iplan-claude`; both are interchangeable here.
`--land` needs the workspace to be a git repository.

```bash
pip install -e "./platforms/hermes[dev]"

# 1. Intake: normalize + validate the SDD-IPLAN
iplan-hermes intake examples/IPLAN-EXAMPLE.yaml

# 2. Run end-to-end in a fresh git workspace, committing if green
ws="$(mktemp -d)" && git init -q "$ws"
iplan-hermes run examples/IPLAN-EXAMPLE.yaml \
  --actions examples/actions.yaml --workspace "$ws" \
  --land --branch iops/example

# 3. Inspect the recorded run
iplan-hermes status

# 4. Validate the monitoring manifest and check SLOs against samples
iplan-hermes monitor validate examples/monitoring.yaml
printf 'availability_ratio: 99.95\n' > "$ws/samples.yaml"
iplan-hermes monitor slo-check examples/monitoring.yaml "$ws/samples.yaml"
```

After step 2 the workspace has a commit on `iops/example` containing
`src/greeting.py` + `tests/test_greeting.py`, and the handover result is
`completed` with that commit recorded.

## Ledger signing + verification

Signing is config-gated: the engine signs the landed ledger when its
`Config.signing_key` is set (secrets come from the environment — see
`framework/config/CONFIG_CONTRACT.md`). Programmatically:

```python
from iplan_hermes import HermesEngine

engine = HermesEngine()
engine._config.signing_key = "your-signing-key"   # or load_config() from env
landed = engine.land(ledger, workspace, branch="iops/example",
                     actor={"id": "op", "role": "operator"})
assert engine.verify_ledger(landed.ledger) is True
```

The full, asserted version of this walkthrough — committed + green + monitored
+ signed, on **both** engines — is the acceptance test at
`platforms/<engine>/tests/test_acceptance.py`.

## Monitoring

`evaluate_alerts(manifest, samples)` fires an alert when a referenced SLO is not
met (sample `<` objective):

- healthy sample `{availability_ratio: 99.95}` → `[]` (objective is `99.9`)
- breaching sample `{availability_ratio: 90.0}` → `[ALERT-001]`
