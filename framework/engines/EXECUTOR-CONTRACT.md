# Executor Contract

The orchestrator (see `framework/execution/RUN_MODEL.md`) is **executor-agnostic**
(D-0013): it drives the task graph and records the ledger, delegating "how a task
gets done" to a pluggable `Executor`. The expensive governance core is written
once per engine; the executor is the swappable seam.

## Interface

```python
class Executor(Protocol):
    def execute(self, task: dict, ctx: ExecutionContext) -> ExecutorResult: ...
```

```python
@dataclass
class ExecutionContext:
    task: dict                 # the task_graph node
    isolation_scope: dict      # client_id / project_id / allowed_roots
    clock: Callable[[], str]   # injected; returns an ISO-8601 timestamp
    ids: Callable[[str], str]  # injected; ids("L") -> "L1", "L2", ...

@dataclass
class ExecutorResult:
    outcome: str                       # "success" | "failure"
    touched_paths: list[str]           # paths edited (must be within allowed_roots)
    evidence: dict | None = None       # {kind, summary, location} or None
    reason: str | None = None          # failure reason (-> blocked_reason)
    retriable: bool = False            # a retriable failure (the saga may retry)
```

A `retriable` failure (e.g. a transient error or a reported timeout) is retried
by the saga up to `max_retries` with injected backoff `sleep`; a non-retriable
failure (or exhausted retries) escalates to a blocker (see
`framework/execution/SAGA_EXECUTION_MODEL.md`).

The orchestrator interprets the result per RUN_MODEL: `success` with evidence →
`completed` with a passing acceptance; `success` without evidence → optimistically
`completed` (the gate then vetoes via `LEDGER.EVIDENCE_REQUIRED`); `failure` →
`blocked` with a blocker.

## Executor kinds

- `MockExecutor(outcomes)` — deterministic; returns the scripted result for a
  `task_id`, defaulting to `success` (no paths, no evidence) when unscripted.
  Used for tests + scenario conformance.
- `HostRuntimeExecutor` / `ApiExecutor` — live executors (Phase 8); drive a host
  agent runtime, or call a model API. Not in this phase.

## Scenario `mock_outcomes` schema

A scenario scripts the `MockExecutor`:

```yaml
mock_outcomes:
  T1: {outcome: success, touched_paths: ["src/a.py"], evidence: {kind: test, summary: "ok", location: "ci://1"}}
  T2: {outcome: failure, reason: "tests failed"}
  # unscripted task -> default success (no paths, no evidence)
  # an optional per-attempt sequence (consumed one-per-call, last repeats):
  T3: {attempts: [{outcome: failure, retriable: true}, {outcome: success, evidence: {kind: test, summary: ok, location: x}}]}
```

`MockExecutor` is stateful per task across attempts (a per-task call counter), so
the saga's retry loop sees the scripted sequence. `clock` and `sleep` are injected
(D-0014); executors must not call ambient `datetime.now()` / `time.sleep`.

## Determinism

`clock` and `ids` are injected (D-0014) and are the **only** sources of time and
identifiers in the run. Executors must not call ambient `datetime.now()` /
`uuid4()`; they receive `ctx.clock` / `ctx.ids` if needed.
