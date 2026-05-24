# Evidence Contract

How real **evidence** is produced — the "green" half of "committed + green". An
executor runs a task's acceptance **checks** and records the result as an
`execution_evidence` entry; a completed task must carry passing evidence (the
gate's `LEDGER.EVIDENCE_REQUIRED` / `LEDGER.ACCEPTANCE_WEAK` rules).

## Checks

A check is `{name, command}` where `command` is an **argument list** (run with
no shell, `shell=False`). The evidence runner executes each check in the
workspace and captures `{name, exit_code, output}`.

```
run_checks(checks, workspace) -> {passed: bool, results: [{name, exit_code, output}]}
```

`passed` is true iff **every** check exits `0`. Captured `output` is **redacted**
(below) before it is returned or stored.

## ScriptedExecutor action script

`ScriptedExecutor(spec, workspace)` consumes, per task:

```yaml
mock_outcomes:        # (reused key name) action script keyed by task_id
  T1:
    actions:
      - {type: write, path: "src/a.py", content: "..."}
      - {type: command, cmd: ["python", "-c", "print('hi')"]}
    checks:
      - {name: "tests", command: ["python", "-c", "import sys; sys.exit(0)"]}
```

The executor applies `actions` in order (each sandbox-gated), runs `checks`, and
returns an `ExecutorResult`: `touched_paths` = written paths, `evidence` built
from the check results, `outcome: success` iff all actions applied and all checks
passed, else `failure` with a `reason`.

> Action **generation** (deciding the actions/checks) is the live executor's job
> (Phase 8). Here the script is pre-written.

## Redaction

```
redact(value, secrets) -> value with each secret replaced by "***"
```

Deterministic: secrets are processed **longest-first** so overlapping secrets
redact predictably. Applied to all captured command output before it enters the
append-only ledger. Secrets are sourced from the engine `Config` (default empty);
real secret management is Phase 7.

## Partial effects (Phase 4 limitation)

If a multi-action task fails partway, earlier writes persist and the task is
`blocked`. Compensation/rollback of partial effects is **PLAN-005** (saga); a
Phase-4 run is not transactional.
