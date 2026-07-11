# PLAN-024 — Real executor client adapters (first-real-run enablement)

**Status:** draft → ready-for-build pending independent review
**Created:** 2026-07-10
**Owner repo:** iplan-runner (public OSS, MIT; two engines: `platforms/claude`,
`platforms/hermes`)
**Wave:** the last live-execution gap — the executor **seam** (PLAN-022 repo→workspace
clone + PLAN-023 config-selected executor) shipped, but every selectable mode runs a
**stub** client, so the runner makes no real code changes. This plan wires the real
clients + a wall budget so a first *real* run is possible.

> **PLAN number:** `plans/HANDOFF.md:134` reserves **PLAN-024 = "real client adapters"**
> — this plan. A separate branch `plan/PLAN-024_l1-intake-provenance-gate` mis-took the
> number (the L1 intake gate); reconciling that duplicate is TODO-P5 hygiene and does not
> block this plan. This file is the canonical PLAN-024 per the doc of record.

> **Engine parity:** the executor is the **engine-specific** seam (claude ships
> `HostRuntimeExecutor` over a `RuntimeClient`; hermes ships `ApiExecutor` over a
> `ModelClient`) — NOT byte-identical twins. Each fix lands in its own engine; the
> shared modules (`budget.py`, `config.py`, `receiver/`) stay in lockstep.

## Why this exists

A dispatched task today: the receiver claims it, clones the repo (PLAN-022), and runs
`make_executor` — which defaults to `MockExecutor` (`receiver/service.py:82`), and even
the config-selected `api`/`host` modes wire a **stub** client (`cli/commands.py:192` in
both engines). So the full dispatch → clone → "execute" → sign → ingest → project loop
runs correctly end-to-end but produces canned/empty results. A first real run needs: (1)
the real model / host-runtime client wired, and (2) a wall budget so the M-wall timeout
(PLAN-025 #74) actually fires on a hung real client — today it is inert.

## Scope — findings → fixes

### P1 (BLOCKER — the real client adapters)

| ID | Finding | Fix |
| --- | --- | --- |
| R1 | **hermes `api` mode hard-wires the stub model client.** `_executor_factory("api")` builds `engine.api_executor(StubModelClient(), workspace)` (`cli/commands.py:192`), but a **real** client already exists — `get_model_client("anthropic", model, api_key)` → `_AnthropicClient` (calls the real Anthropic Messages API, `model/client.py:51`,`:32`). It is just never routed from config. | Add config for the real model client (`receiver.model_provider` / `model` / `api_key_env`, default absent → keep the stub) and change `_executor_factory("api")` to build the real `ModelClient` via `get_model_client` when configured, else the stub. `_AnthropicClient` needs the optional `[anthropic]` extra + an API key (integration-only, `model/client.py:35`), so the real path is env/extra-guarded. **Note (independent review):** wiring the client is low-effort, but a *reliably succeeding* real run also needs prompt/parse hardening — `build_prompt` (`api.py:17`) does not specify the action sub-schema or strip markdown fences, so a real model's fenced/prose JSON makes `parse_actions` return `None` → `unparseable model output` (`api.py:70`). R1 wires the transport; robust action-generation (a schema-pinned prompt + fence-tolerant parse) is part of R1 or an immediate follow-on. |
| R2 | **claude `host` mode has NO real client — only the Protocol + stub.** `_executor_factory("host")` wires `engine.host_executor(StubRuntimeClient(), workspace)` (`cli/commands.py:192`); `runtime/client.py` ships only the `RuntimeClient` Protocol + `StubRuntimeClient` (`runtime/client.py:23`). There is no adapter that drives a real host agent. | **Build** a real `RuntimeClient` adapter (the Claude Code / host-agent hook): given `(task, workspace)`, drive the host agent over the cloned workspace, then return a `RuntimeResult(success, changed_files, output, usage)` — `changed_files` from a post-run `git` diff of the workspace (the `HostRuntimeExecutor` governor already re-checks each changed path against `allowed_roots`, so scope is enforced downstream). Route it from config alongside R1. Higher effort — external-tool integration; keep it behind the same env/extra guard so CI stays offline. |

### P2 (HIGH — the wall budget; M-wall is inert without it)

| ID | Finding | Fix |
| --- | --- | --- |
| R3 | **The M-wall timeout can't fire in the receiver.** `api_executor`/`host_executor` default `budget=None` → `Budget()` → `max_wall_s=None`, and `run_with_deadline` runs the client call **inline with no timeout** when `max_wall_s is None` (`engine.py:113`/`:118`, `budget.py:26`). The receiver factory passes no budget, and there is no wall-budget config field (`config.py:47` has only `receiver_executor`). So the moment a real (hangable) client is wired, a hung task again holds the `slots` permit forever → permanent `503 receiver_busy` — the exact bug M-wall (#74) fixed at the executor but which is unreachable without a budget. | Add a `receiver.max_wall_s` (and `max_tokens` / `max_cost_usd`) config, build a `Budget` from it, and thread it into `_executor_factory` → `api_executor(client, workspace, budget)` / `host_executor(client, workspace, budget)`. Document a sane default wall for a real run. This makes M-wall live for the real path. |

### P3 (MEDIUM — the first live handshake; INT-1, joint with iplanic PLAN-100 P6)

| ID | Finding | Fix |
| --- | --- | --- |
| R4 | **No test drives the two processes together.** Every runner test mocks iplanic and vice-versa; a first real run would be the first time the real receiver and a real iplanic app have ever talked (the B2/B3 wire mismatches were invisible for exactly this reason). | Stand up a cross-repo integration test: a real receiver + a real iplanic app instance over loopback, exercising register → dispatch (with `dispatch_token_id`) → clone → execute (a **recorded/replayed** model response so CI stays offline, or gated behind `IPLAN_FAKE_IPLANIC`-style env) → emit signed event → iplanic ingest → projection leaves `Queued`. Owned jointly; can live in either repo's CI. This is the test that verifies the first real handshake before it happens in production. |

## Out of scope / deferred

- **M-crash** (startup re-drain of a task orphaned in `running`) and **M-rotation**
  (emitter key rotation) — deferred in PLAN-025; independent of the real client.
- **Non-Anthropic model providers** — `get_model_client` raises `NotImplementedError`
  for other providers (`model/client.py:54`); add when a second provider is needed.
- **A `max_cost_usd` budget is inert for the real Anthropic path** — `_AnthropicClient`
  reports `cost_usd: 0.0` (`model/client.py:48`), so only the token + wall budgets can
  trip; wire real cost accounting (from the API usage) when a cost cap is needed.
- **mTLS / OIDC inbound auth at the receiver** — deferred (bearer today).
- **The wall-budget knob does not kill the orphaned worker** — M-wall frees the slot but
  the abandoned daemon thread / host subprocess keeps running (documented in #74); a real
  host adapter (R2) should additionally terminate its subprocess on timeout where it can.

## Verification

- Both engines' suites green after each change:
  `PYTHONPATH=platforms/claude/src python -m pytest platforms/claude -q` and the hermes
  twin; `tests/conformance`.
- New tests: R1 — config routes `get_model_client` (a real client is built when
  configured; the stub is the default) without importing `anthropic` in CI (inject a fake
  `ModelClient`); R2 — the host adapter over a fake/recorded host agent returns the right
  `RuntimeResult` + `changed_files`; R3 — a configured `max_wall_s` threads a `Budget` so a
  hung injected client returns `BUDGET.TIME_EXCEEDED` and the slot releases (reuse the
  `Event`-blocking client pattern from #74); R4 — the loopback two-process harness.
- Keep the two engines' shared modules byte-identical; the executor seam stays
  engine-specific.

## Cross-repo sequencing

R1 (hermes real model client — the client already exists) is the shortest path to a real
run; R2 (claude host adapter — a new build) is the larger piece; R3 (wall budget) pairs
with either and must land before a real run so a hung agent can't wedge the receiver; R4
(INT-1) is joint with iplanic PLAN-100 P6 and verifies the first handshake.

## Claim ledger

| # | Claim | Symbol | Citation |
| --- | --- | --- | --- |
| 1 | `make_executor` defaults to `MockExecutor` via `engine.default_executor()` | `default=lambda engine, _workspace: engine.default_executor()` | platforms/hermes/src/iplan_hermes/receiver/service.py:82 |
| 2 | `default_executor()` returns `MockExecutor()` | `return MockExecutor()` | platforms/hermes/src/iplan_hermes/engine.py:118 |
| 3 | hermes `api` mode hard-wires `StubModelClient` | `engine.api_executor(StubModelClient(), workspace)` | platforms/hermes/src/iplan_hermes/cli/commands.py:192 |
| 4 | a real model client exists: `get_model_client("anthropic", …)` → `_AnthropicClient` | `def get_model_client` | platforms/hermes/src/iplan_hermes/model/client.py:51 |
| 5 | `_AnthropicClient` is integration-only (needs the anthropic extra + api_key) | `class _AnthropicClient` | platforms/hermes/src/iplan_hermes/model/client.py:32 |
| 6 | claude `host` mode hard-wires `StubRuntimeClient` | `engine.host_executor(StubRuntimeClient(), workspace)` | platforms/claude/src/iplan_claude/cli/commands.py:192 |
| 7 | no real `RuntimeClient` adapter — only the Protocol + stub | `class StubRuntimeClient` | platforms/claude/src/iplan_claude/runtime/client.py:23 |
| 8 | `api_executor` takes an optional `budget` defaulting to `None` | `budget: Budget | None = None` | platforms/hermes/src/iplan_hermes/engine.py:113 |
| 9 | `run_with_deadline` runs inline (no timeout) when `max_wall_s is None` | `if max_wall_s is None:` | platforms/hermes/src/iplan_hermes/budget.py:26 |
| 10 | config has `receiver_executor` (mock default) and no wall-budget field | `receiver_executor: str = "mock"` | platforms/hermes/src/iplan_hermes/config.py:47 |
| 11 | HANDOFF reserves PLAN-024 = real client adapters | `next **plan** = **PLAN-024** (real client adapters` | plans/HANDOFF.md:134 |
| 12 | the `HostRuntimeExecutor` governor re-checks each changed path against `allowed_roots` (R2's scope-safety) | `classify_path(path, roots)` | platforms/claude/src/iplan_claude/executor/hostruntime.py:58 |
| 13 | the receiver clones the repo per task (R2's git-diff needs a git workspace) | `clone(repo["url"], repo["base_ref"], dest)` | platforms/hermes/src/iplan_hermes/receiver/service.py:63 |
| 14 | `_AnthropicClient` reports `cost_usd: 0.0` (a cost budget is inert for the real path) | `cost_usd` | platforms/hermes/src/iplan_hermes/model/client.py:48 |

## Review log

### Pass 1 — 2026-07-10 — author (self)
Drafted from a first-real-run readiness audit. Verified citations 1-11 by opening each
file. R2 (build the claude host adapter) is the load-bearing effort — there is no real
`RuntimeClient` today; R1 (hermes) is a routing change over an existing `_AnthropicClient`.
R3 is small but a hard prerequisite (M-wall is inert without a budget). R4 is the joint
first-handshake test.
**Result:** pending independent review (Pass 2 required before ready).

### Pass 2 — 2026-07-10 — independent
Fresh-context adversarial review against the real source. **All 11 original citations
resolve exactly; zero fail.** The per-engine cross-check confirmed: BOTH engines
hard-wire a stub at the same `cli/commands.py:192` (hermes `StubModelClient`, claude
`StubRuntimeClient`) and neither passes a budget. Verified: `_AnthropicClient.complete`
returns the `ModelResponse` shape `ApiExecutor` consumes; `StubRuntimeClient` is the ONLY
`run_task` impl in the claude tree (R2's "no real adapter" is accurate); `RuntimeResult`
is the shape `HostRuntimeExecutor` consumes and the governor's `allowed_roots` re-check is
real; M-wall is genuinely inert in the receiver path and threading a `Budget` through the
factory is the complete fix (the only other executor-construction site, `commands.py:337`,
is the interactive CLI `run`, correctly out of scope). **Zero load-bearing (false)
findings.** Folded four refinements: (F1) R1's real run also needs prompt/parse hardening
— added to the R1 fix note, not just a client swap; (F2) added ledger rows 12-13 for the
`allowed_roots` re-check + the per-task clone that R2's correctness rests on; (F3) added a
ledger row 14 + out-of-scope note that a `max_cost_usd` budget is inert for the Anthropic
path; (F4) corrected the `model/client.py:55`→`:54` reference. No claim was false; the plan
asserts a real run becomes *possible*, which the source supports.
**Result:** ready.
