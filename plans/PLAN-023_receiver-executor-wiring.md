# PLAN-023 — Config-selected receiver executor (D-0025)

**Status:** ready-for-build (independent review PASS — zero load-bearing findings, 1 minor fold applied)
**Decision:** D-0025 · **Engines:** claude (`host`) + hermes (`api`) — engine-specific, NOT byte-parallel · **Date:** 2026-07-05

## Problem

PLAN-022 (D-0024) gave the receiver an **injectable executor seam** — `ReceiverDeps.make_executor`
(`receiver/service.py:81`) — but the CLI still builds `ReceiverDeps` **without** it
(`cli/commands.py:201`), so the receiver always runs the default `MockExecutor`. Each engine already
ships its **real-agent executor** + governor + a CI stub client, unused by the receiver:

- **claude (B-style, D-0013):** `HostRuntimeExecutor` (`executor/hostruntime.py:19`) drives a host agent
  runtime via `RuntimeClient`, then governs the result (budget + scope). `engine.host_executor(client,
  ws, budget)` (`engine.py:114`); `StubRuntimeClient` (`runtime/client.py:23`) for CI.
- **hermes (A-style, D-0013):** `ApiExecutor` (`executor/api.py:32`) asks a `ModelClient` to propose
  actions, then applies + budget-checks. `engine.api_executor(client, ws, budget)`
  (`engine.py:109`); `StubModelClient` (`model/client.py:21`) for CI.

This slice **wires the receiver to config-select** its executor via the PLAN-022 seam, so an operator
can run the real governor instead of the mock — and the **real** client adapter becomes a pure drop-in.

## Scope (minimal-and-realistic)

- **`Config.receiver_executor: str = "mock"`** — a new receiver config field (loaded from the
  `receiver.executor` YAML key), values per engine: claude `mock`|`host`, hermes `mock`|`api`.
- **`cli/_server` builds `make_executor` from the config** and threads it into `ReceiverDeps`: `mock` →
  today's `engine.default_executor()`; `host` (claude) → `engine.host_executor(StubRuntimeClient(), ws)`;
  `api` (hermes) → `engine.api_executor(StubModelClient(), ws)`; an unknown mode **fails loud** (emit
  error + non-zero exit, like the other `_server` guards).
- Both engines get the field + selector; the **selector branch is engine-specific** (`host` vs `api`) —
  allowed because the "spec parity" gate is **not** a source diff (it enforces only the shared framework
  spec version + strict no-cross-engine-imports, `tests/conformance/test_engines.py:22`), exactly as the
  already-divergent `executor/hostruntime.py` (claude) vs `executor/api.py` (hermes) pass today.

**Out of scope (named, deferred to PLAN-024 — integration-only):** the **real client adapters** — claude's
Claude Code hook `RuntimeClient` (unbuilt; "integration-only", `runtime/client.py:2`) and hermes's real
model client (`get_model_client(provider, model, api_key)`, `model/client.py:51`, import-guarded behind
the `[anthropic]` extra + credentials). This slice wires the **stub** clients only, so it stays fully
CI-able; PLAN-024 swaps the stub for the real client (a config-guarded factory) + integration tests. Also
deferred (D-0022 backlog): per-executor budget config, `scripted` mode, auto re-drain, crash-recovery,
inbound auth.

## Design

### 1. `Config.receiver_executor` (both engines)

Add after `receiver_workspace` (`config.py:46`): `receiver_executor: str = "mock"`. Load it from the YAML
`receiver.executor` key by adding `"executor"` to the existing receiver str-field load loop
(`config.py:89`, `for str_field in ("bind", …, "workspace")`) — so `setattr(cfg, "receiver_executor",
str(receiver["executor"]))` when present. Default `"mock"` preserves today's behavior with no config.

### 2. `cli/_server` executor selection (engine-specific)

Before building `ReceiverDeps` (`cli/commands.py:201`), build the factory. **claude:**

```python
def _executor_factory(mode: str) -> Callable[[ClaudeEngine, str], Executor]:
    if mode == "mock":
        return lambda engine, _ws: engine.default_executor()
    if mode == "host":
        return lambda engine, ws: engine.host_executor(StubRuntimeClient(), ws)
    raise ValueError(f"unknown receiver.executor {mode!r} (want 'mock' or 'host')")
```

**hermes** is identical in shape with `mode == "api"` → `engine.api_executor(StubModelClient(), ws)` and
the message `"want 'mock' or 'api'"`. `_server` calls it inside a guard mirroring the existing
`endpoint`/`token` checks:

```python
    try:
        make_executor = _executor_factory(cfg.receiver_executor)
    except ValueError as exc:
        _emit({"error": str(exc)})
        return 1
    deps = ReceiverDeps(… , make_executor=make_executor)
```

`StubRuntimeClient`/`StubModelClient` are imported at the top of `cli/commands.py` (claude:
`from ..runtime.client import StubRuntimeClient`; hermes: `from ..model.client import StubModelClient`).
**Implementation note:** the `_executor_factory` return annotation `Callable[[…Engine, str], Executor]`
also needs `from collections.abc import Callable` + `from ..executor.base import Executor` added to
`cli/commands.py` (both engines currently import neither). Budget is left at the `Budget()` default
(unlimited — per-executor budget config is deferred).

**Why the stub still adds value over `mock`:** `host`/`api` mode runs the **real governor** —
`HostRuntimeExecutor` enforces budget + rejects out-of-scope `changed_files`
(`executor/hostruntime.py`); `ApiExecutor` parses the model spec + budget-checks (`executor/api.py`) — so
the receiver exercises the governance path end-to-end, and PLAN-024's real client is a one-line swap.

### 3. What PLAN-024 changes (named, not built here)

`_executor_factory`'s `StubRuntimeClient()` / `StubModelClient()` become a config-guarded real-client
selection (claude: the real Claude Code hook adapter once it exists; hermes: `get_model_client(provider,
model, api_key)` from `receiver.model.*` config) — no other receiver change.

## Verification (all CI-able, no network)

Per engine (engine-specific — not byte-parallel):

- **`Config.receiver_executor`** — loads from `receiver.executor` YAML; default `"mock"`.
- **`_executor_factory`** — `"mock"` → an executor equal to `engine.default_executor()`'s type
  (`MockExecutor`); `"host"`/`"api"` → a `HostRuntimeExecutor`/`ApiExecutor` bound to the given workspace
  (isinstance check); an unknown mode → `ValueError`.
- **`execute` with the real governor** — a `ReceiverDeps(make_executor=_executor_factory("host"|"api"))`
  drives a dispatched task through `HostRuntimeExecutor(StubRuntimeClient())` / `ApiExecutor(
  StubModelClient())`: the run drains events + settles `done` (the stub's canned success passes the
  empty-`changed_files` scope check / the `"{}"` no-action apply). Proves the receiver runs the real
  governor, not the mock.
- **Backward-compat** — with no `receiver.executor` config, the receiver behaves exactly as today
  (`mock` → `MockExecutor`); the existing receiver suites stay green.

## Risks

| # | Risk | Mitigation |
| --- | --- | --- |
| 1 | Engine-specific `_server` wiring breaks "spec parity" | Parity is version + no-cross-import only (`test_engines.py:22`), not a source diff — hostruntime.py/api.py already diverge and pass |
| 2 | `host`/`api` with a stub client is ≈ mock (low value) | It runs the real **governor** (budget + scope), the material difference; the real client is a PLAN-024 config-swap |
| 3 | An operator sets `host` on hermes / `api` on claude | `_executor_factory` fails loud (`ValueError` → `_emit` error + exit 1); each engine accepts only its own mode |
| 4 | Budget unbounded (`Budget()`) lets a runaway runtime burn cost | Named deferral (per-executor budget config); the governor still enforces scope; MVP posture |

## Proposed decision — D-0025

Wire the receiver to config-select its executor (`receiver.executor`: `mock` default / `host` claude /
`api` hermes) through the PLAN-022 `make_executor` seam, using each engine's existing governor + **stub**
client. Engine-specific by design (D-0013). The **real** client adapters (Claude Code hook / real model
API) stay integration-only and are deferred to **PLAN-024** as a config-guarded drop-in.

## Claim ledger

| # | Claim | Symbol | Citation |
| --- | ----- | ------ | -------- |
| 1 | `ReceiverDeps.make_executor` (PLAN-022 seam) — the injection point this slice drives from config | `make_executor: Callable` | platforms/claude/src/iplan_claude/receiver/service.py:81 |
| 2 | `cli/_server` builds `ReceiverDeps(...)` today **without** `make_executor` (→ default Mock) — where the config selector threads in | `deps = ReceiverDeps(` | platforms/claude/src/iplan_claude/cli/commands.py:201 |
| 3 | `Config.receiver_workspace` — the receiver config block a `receiver_executor` field joins | `receiver_workspace` | platforms/claude/src/iplan_claude/config.py:46 |
| 4 | The receiver str-field YAML load loop — add `"executor"` so `receiver.executor` sets `receiver_executor` | `for str_field in` | platforms/claude/src/iplan_claude/config.py:89 |
| 5 | claude `engine.host_executor(client, ws, budget)` — the `host` mode factory | `def host_executor` | platforms/claude/src/iplan_claude/engine.py:114 |
| 6 | hermes `engine.api_executor(client, ws, budget)` — the `api` mode factory | `def api_executor` | platforms/hermes/src/iplan_hermes/engine.py:109 |
| 7 | `engine.default_executor()` returns `MockExecutor` — the `mock` default (today's behavior) | `def default_executor` | platforms/claude/src/iplan_claude/engine.py:122 |
| 8 | `StubRuntimeClient` — claude's CI host client (real Claude Code hook = PLAN-024) | `class StubRuntimeClient` | platforms/claude/src/iplan_claude/runtime/client.py:23 |
| 9 | `StubModelClient` — hermes's CI api client (real `get_model_client` = PLAN-024) | `class StubModelClient` | platforms/hermes/src/iplan_hermes/model/client.py:21 |
| 10 | `HostRuntimeExecutor` governs budget + rejects out-of-scope `changed_files` — what `host` mode exercises beyond mock | `class HostRuntimeExecutor` | platforms/claude/src/iplan_claude/executor/hostruntime.py:19 |
| 11 | `ApiExecutor` parses a model spec + budget-checks — what `api` mode exercises beyond mock | `class ApiExecutor` | platforms/hermes/src/iplan_hermes/executor/api.py:32 |
| 12 | "spec parity" = strict no-cross-engine-imports (+ shared spec version), **not** a source diff — so engine-specific `_server` wiring is allowed | `def test_strict_isolation` | tests/conformance/test_engines.py:22 |
| 13 | hermes's real model-client factory `get_model_client(provider, model, api_key)` — the PLAN-024 injection point (integration-only) | `def get_model_client` | platforms/hermes/src/iplan_hermes/model/client.py:51 |
| 14 | claude's real runtime adapter is integration-only + unbuilt (PLAN-024) | `integration-only` | platforms/claude/src/iplan_claude/runtime/client.py:2 |
| 15 | D-0013 pluggable executor — why claude (`host`, B-style) and hermes (`api`, A-style) legitimately differ | `### D-0013` | plans/DECISIONS.md:132 |

## Review log

### Pass 1 - 2026-07-05 - author self-review

- **Engine-specific by design, not a parity break.** The `_server` selector branches `host` (claude) vs
  `api` (hermes) — the engines' real executors already diverge (`hostruntime.py` vs `api.py`) and pass
  the version+isolation parity. Flagged for the reviewer to confirm the "spec parity" gate is not a
  source diff and that the branch imports only its own engine's stub (no cross-import).
- **Stub-only keeps it CI-able; the value is the governor.** `host`/`api` with the stub still runs the
  real budget+scope governance (unlike mock's no-op), and makes PLAN-024's real client a one-line swap.
  Recorded the honest limitation (stub ≈ mock at the *effect* level) in Risk 2.
- **Default `mock` = byte-for-byte today.** No `receiver.executor` config → `MockExecutor`, existing
  suites unchanged. Confirm.
- **Budget unbounded (`Budget()`).** Named deferral; the governor still enforces scope. Confirm this is
  acceptable for the MVP or should carry a default cap.

### Pass 2 - 2026-07-05 - independent (fresh-context `code-reviewer` agent)

**15/15 ledger claims TRUE (line-precise); verdict READY, zero load-bearing findings.** The reviewer
traced the design end to end on **both** engines and confirmed:

- **Signature match:** `host_executor(client, workspace=".", budget=None)` / `api_executor(client,
  workspace=".", budget=None, secrets=None)` both accept `(client, ws)` with budget defaulting; the
  factory lambdas' `(engine, ws)` match the seam's `deps.make_executor(deps.engine, workspace)` call
  (`service.py:100`).
- **Host/api-with-stub reaches `success` on both engines** — claude: `StubRuntimeClient` →
  `RuntimeResult(success=True, changed_files=[])` → `Budget()` unlimited passes + empty scope passes →
  `success`; hermes: `StubModelClient` → `text="{}"` → `parse_actions` returns `{}` (a dict, not `None`,
  passes the guard) → `apply_task_spec({})` no-ops → `success`. **No** stub-output path makes the governor
  fail. So the run drains + settles `done`.
- **"spec parity" is version-marker + strict-no-cross-import only, NOT a source diff** — engine-specific
  `host`/`api` branches are legal (as `hostruntime.py` vs `api.py` already are); the factory's relative
  imports (`..runtime.client` / `..model.client`) never name the sibling package → no cross-import.
- **Config load** confirmed: adding `"executor"` to the str-field loop sets `receiver_executor` from
  `receiver.executor`; default `"mock"` = byte-for-byte today.

**One MINOR fold, applied:** `cli/commands.py` (both engines) needs `from collections.abc import Callable`
+ `from ..executor.base import Executor` for the `_executor_factory` return annotation. No load-bearing
defects.

**Result:** ready — zero load-bearing findings; the one minor import fold is applied.
