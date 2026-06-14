# Iplanic Remote-Executor Conformance Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins; harden until a
> pass finds nothing.
>
> **Size the plan to the problem.** ~N fixes for N discovered gaps, not N
> speculative features. The surplus a review pass surfaces beyond the original
> gap count is speculative scope — cut it.

**Goal:** Make both engines **conformant remote executors for Iplanic** —
consume Iplanic's runtime **task payload**, honor its `executor_context`, and
emit **signed execution events** in Iplanic's shape — additively, without
changing the standalone run loop.

**Architecture:** Additive (D-0016, new — mirrors D-0014). A new
`framework/remote/` contract + a `remote/` conformance kind. Payload-mode intake
is a **second front door** that produces the *same* `iplan-intake` manifest the
run loop already consumes (PLAN-002/003 unchanged). Event emission is a pure
**projection** of the existing signed ledger into Iplanic's `execution-event`
shape — engine-identity-free, so the cross-engine differential needs no
normalization (D-0012). Engines stay isolated (D-0011); the new code is copied
identically into each. **No live transport** — emission is offline/in-memory;
the HTTP POST to Iplanic's ingestion endpoint is integration-only (behind an
extra), exactly as live executors are (PLAN-008).

**Tech Stack:** Python ≥3.11; `pytest`; `unittest` conformance; `ruff` +
`mypy --strict`; YAML/JSON.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-013 |
| Depends on | `PLAN-001`..`PLAN-012` (DONE); **PLAN-014** (canonical signing — see Re-grounding); D-0011..D-0015; engine ledger event_types (`orchestrator/loop.py`); Iplanic contracts (vendored copies, re-pinned to the frozen standard — see below) |
| Status     | DONE - 2026-06-11 (re-grounded; implemented) |
| Feeds      | IOPS plugged into Iplanic as a hosted remote executor; signed log-ingestion upstream |

## Re-grounding (2026-06-11)

This plan was authored **before** the Iplanic IPLAN standard was frozen
(Iplanic PLAN-001…008, decisions D-0021…D-0028, landed 2026-06-09…06-11). Two
load-bearing corrections follow; the payload-intake and event-projection
scaffolding is otherwise unchanged.

1. **Signing is incorrect for conformance and is split to PLAN-014.** The Approach
   originally reused `security.signing.sign_event` (HMAC over IOPS's own
   `json.dumps(sort_keys)` canonical form, excluding only `signature`). Iplanic's
   now-normative `iplan-canonical-json` is **RFC 8785 JCS over `sha256`** with
   recursive **drop-null** and a signed payload that excludes **`{signature,
   received_at}`**, keyed with the **raw** key bytes, and supports **ed25519** as
   well as `hmac-sha256`. The two do **not** match — verified differentially
   against Iplanic's golden `sig_hmac` vector (IOPS `7ce5…` ≠ Iplanic `bcac…`),
   and IOPS currently **signs `received_at`**, which Iplanic overwrites at ingest,
   so the signature would fail verification. Adopting `iplan-canonical-json` is the
   conformance prerequisite and is its own focused plan, **PLAN-014**; event
   emission here consumes PLAN-014's canonical signer instead of `sign_event`.
2. **Conformance validates against Iplanic's golden vectors.** The vendored mirrors
   are re-pinned to the frozen schemas (`schema_version 1.2-draft`), and the
   conformance suite vendors and reproduces Iplanic's `canonicalization`,
   `status_projection`, and `scope_check` vectors — the shared contract — rather
   than asserting field-presence alone.

## Objective

The architecture is three layers, not two: **SDD** authors the IPLAN, **Iplanic**
owns the hosted execution control plane (plan lifecycle, order, executor
assignment, completion gate, signed logs), and **IOPS** is a **remote AI
execution worker**. IOPS today only speaks its own `iplan-intake` manifest and
keeps signed events inside its ledger. To be dispatchable by Iplanic it must
close **three** concrete gaps from the handoff's mapping table, plus prove them:

1. **Payload-mode intake** — consume Iplanic's `IPLAN-TASK-TEMPLATE.yaml`
   runtime payload (which binds intent to `run_id`/`step_id`/`executor_id`/lease/
   `work_order`/`context_package`), mapping its `step_id → work_order_id →
   todo_id` hierarchy onto the engine's flat task model **and** preserving the
   Iplanic identity for event emission.
2. **Signed log-ingestion (shape only)** — project the engine's HMAC-signed
   ledger events into Iplanic's `execution-event` shape (its required fields +
   `signature: {key_id, algorithm, value}`), reusing the existing `sign_event`.
3. **`executor_context` honoring** — enforce the payload's `forbidden_paths`
   in the sandbox, and **reject** a payload that omits required context
   ("executor must not infer missing context").
4. **Boundary conformance** — golden vectors proving payload acceptance, event
   shape, and context enforcement, replayed per engine + cross-engine
   differential.

Standalone IOPS keeps working unchanged: payload-mode is purely additive.

## Scope

**In:**

1. `framework/remote/REMOTE_EXECUTOR_CONTRACT.md` — the consumed payload subset,
   the **payload → `iplan-intake` mapping**, the **ledger-event → execution-event
   mapping table** (engine event kind → Iplanic `event_type`/`status`), the
   context-enforcement rules, and the offline/transport-agnostic boundary.
2. Vendored, **version-pinned** mirrors (no dependency on the Iplanic repo, per
   the same principle as "no dependency on the SDD repo"):
   `framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml` (consumed subset) and
   `framework/remote/EXECUTION-EVENT-TEMPLATE.yaml` (emitted required-field
   list). Each carries the upstream `source` + version it mirrors.
3. New rules in `framework/conformance/rule-ids.yaml`: category `REMOTE-001`
   with `REMOTE.PAYLOAD_*` (intake of the payload) findings; plus the new
   sandbox decision reason `SANDBOX.FORBIDDEN` documented in the sandbox
   contract (sandbox reasons are pinned by sandbox vectors, not rule-ids).
4. `remote/` conformance kind: payload-intake samples + event-projection samples
   (`framework/conformance/remote/<name>/{payload,ledger,expect}.yaml`).
5. Per engine (copied identically, no cross-import):
   - `intake/payload.py` — `ingest_task_payload(path, config) -> manifest`.
   - `validation/payload_rules.py` — pure `REMOTE.*` payload validator.
   - `ledger/events.py` — `to_execution_events(ledger, payload, key, key_id, *,
     ids) -> list[event]` (pure projection; injected id source; reuses
     `security.signing.sign_event`).
   - `effectors/sandbox.py` — extend `classify_path(path, allowed_roots,
     forbidden_paths=())` with `SANDBOX.FORBIDDEN`.
   - `engine.py` — extend the adapter wrapper `classify_path` to forward
     `forbidden_paths` (so conformance can reach the new reason).
   - `cli/commands.py` — `intake --payload <file>` and `emit-events <ledger>
     --payload <file> [--key-env]`.
   - tests.
6. Registry: add the contract doc, the two templates, `remote_root`; bump
   `spec_version`. Atomic spec bump `framework/VERSION` **1.0.0 → 1.1.0**
   (additive → MINOR; backward-compatible) with registry `spec_version` + both
   engines' `FRAMEWORK_SPEC_VERSION` (the conformance-gated markers). Engine
   stream: each `VERSION` **and** `__init__.__version__` `0.11.0 → 0.12.0`
   (kept equal). `pyproject.toml version` (already `1.0.0`, ungated, pre-existing
   divergence) is left untouched — out of scope (see Task 6 Step 1).
7. `tests/conformance/test_remote.py` — per-engine payload→manifest projection +
   event projection equal `expect`; cross-engine differential on both;
   `SANDBOX.FORBIDDEN` parity; registry `remote_root` path check. `CHANGELOG.md`
   `[1.1.0]` + `HANDOFF.md`/`TODO.md`/`ROADMAP.md`/`README.md` updates.

**Out (explicit speculative-scope cuts):**

1. **Live transport** — the actual A2A task fetch and HTTP POST to Iplanic's
   log-ingestion / artifact endpoints. Integration-only, behind an extra, its
   own plan (mirrors PLAN-008's live executors). This plan emits in-memory.
2. **Executor registration runtime** — emitting `executor-registration` to
   Iplanic. Static understanding only; not in the handoff's a/b/c/d. Deferred.
3. **TMP-IPLAN** (source/return handoffs, `return_gate`) — Iplanic first-class
   artifact; add later if needed.
4. **Reworking `run_chain`** for Iplanic's tier/sequence chain model — Iplanic
   owns chain orchestration when plugged in; standalone `run_chain` stays.
5. **Full D-0015 auth wiring** (OIDC/SPIFFE, PDP) — already its own deferred item.
6. **Changes to the SDD or Iplanic repos.**

## Approach

**Two front doors, one manifest.** `ingest_task_payload` mirrors the existing
`ingest_iplan`: it reads the Iplanic payload YAML and **maps** it to the same
`iplan-intake` manifest, so PLAN-003's `run` loop, gate, saga, and evidence
runner are untouched. The mapping:

| `iplan-intake` field | Iplanic payload source |
|---|---|
| `intake_control.source_iplan` | `iplan_id` |
| `intake_control.source_iplan_version` | `plan_version_id` |
| `intake_control.source_iplan_checksum` | `"sha256:" + sha256(file_bytes)` (computed) |
| `intake_control.approved` | `true` — **dispatch is the approval** (Iplanic only dispatches approved work; the `EXEC-Ready ≥90` gate is Iplanic's, not re-derived here) |
| `intake_control.exec_ready_score` | `exec_ready_min` (90 — asserted, not measured) |
| `isolation_scope.client_id` | `org_id` |
| `isolation_scope.project_id` | `project_id` |
| `isolation_scope.allowed_roots` | `["."]` (the repo workspace from `context_package.repository`) |
| `isolation_scope.forbidden_paths` | `context_package.forbidden_paths` (**new**, additive) |
| `task_graph[]` | one entry per `work_order.todos[]`: `{task_id: todo_id, title: description, depends_on: [], acceptance: join(acceptance_criteria)}` |
| `remote_execution` (**new block**, ignored by the run loop) | `{task_id, run_id, step_id, work_order_id, executor_id, iplan_id, plan_version_id, org_id, project_id, protocol_plan_id, protocol_agent_id}` — the Iplanic identity, carried for event emission |

Extra manifest keys are ignored by the loop, so `remote_execution` rides along
safely. `todos` within one work order have no declared inter-dependencies in the
template → `depends_on: []` (sequential execution is the loop's default order).

**Events are a projection, not new state.** `to_execution_events` walks the
already-signed `execution_log` and emits one Iplanic `execution-event` per
ledger event, **dropping the engine's `agent_id`** and using the payload's
`executor_id`. Determinism + parity (R-pattern from PLAN-003/011): an injected
`ids` source supplies `event_id`/`trace_id`; `idempotency_key = f"{run_id}:
{event_id}"`; `occurred_at` is the ledger event's timestamp; `received_at` is set
equal to `occurred_at` for the offline emit (Iplanic overwrites it on ingest).
Because every field comes from the payload + injected ids (never engine
identity), **both engines emit byte-identical events** → the differential needs
no normalization. The `signature` is produced by **PLAN-014's canonical signer**
(`iplan-canonical-json`: RFC 8785 JCS + `sha256`, recursive drop-null, signed
payload excluding `{signature, received_at}`, raw-byte key), **not** the legacy
`security.signing.sign_event`. It returns the three keys the schema demands —
`{key_id, algorithm, value}` where `value` is the lowercase-hex signature and
`algorithm ∈ {hmac-sha256, ed25519}` per the executor's registered key — and emits
**only** those keys (`execution-event.schema.json` sets `additionalProperties:
false` on `signature` and on the event object). The legacy `sign_event` (HMAC over
IOPS's own `json.dumps` canonical, excluding only `signature`) is retained for the
**standalone** ledger but is not used for Iplanic emission — it is not byte-
reproducible by Iplanic (see Re-grounding).

**Event-type mapping.** Most events map **directly** from `execution_log`
entries (each has an `event_type`); the verified full set of appended kinds is
`task_started`, `file_edited`, `task_completed`, `task_blocked`, `commit`,
`compensation` (`orchestrator/loop.py`) and `resolution` (`orchestrator/
control.py`). Only `test.passed`/`test.failed` are **derived** — IOPS records the
acceptance outcome on the task entry (`acceptance.result`, set at
`loop.py:219`) without appending a log event, so test outcome is read from the
task entry. The projection is explicit and total over the kinds IOPS emits;
anything without an Iplanic equivalent is an explicit, documented skip — never
guessed:

| Source in the ledger (verified actual) | Iplanic `event_type` | `status` |
|---|---|---|
| `execution_log` `task_started` | `task.started` | `running` |
| `execution_log` `file_edited` | `file.changed` | `running` |
| `execution_log` `task_completed` | `task.completed` | `succeeded` |
| `execution_log` `task_blocked` | `task.blocked` | `blocked` |
| `execution_log` `commit` (LANDING) | `artifact.created` | `running` |
| completed task `acceptance.result == pass` (derived) | `test.passed` | `running` |
| completed task `acceptance.result != pass` (derived) | `test.failed` | `running` |
| `execution_log` `compensation` | — (skip) | — |
| `execution_log` `resolution` | — (skip) | — |

`compensation` (saga undo of partial writes) and `resolution` (blocker override,
PLAN-009) have **no** equivalent in Iplanic's `event_type` enum, so both are
deliberately skipped (documented), not forced into a wrong mapping. Event order
follows ledger order; each task's derived `test.*` is emitted immediately after
that task's `task_completed`.

**Context enforcement.** The pure `classify_path` gains an optional
`forbidden_paths` (default `()` — backward-compatible for the existing
`effectors/apply.py` / host-runtime callers): a path inside `allowed_roots` but
at/under any forbidden prefix returns `{"allowed": false, "reason":
"SANDBOX.FORBIDDEN"}`, checked **after** the positive jail so
`ESCAPE`/`OUTSIDE_ROOTS` still take precedence. For this to be **reachable
through conformance**, three more surfaces must thread the new arg (verified
gap): the engine adapter wrapper `EngineProtocol.classify_path` (currently
`(self, path, allowed_roots)` — `engine.py:97` in hermes, `:102` in claude — in
each engine), the framework
`SANDBOX_CONTRACT.md` signature, and the sandbox conformance harness
(`tests/conformance/test_sandbox.py:29` + each `framework/conformance/sandbox/*/
input.yaml`, which today carry only `path`/`allowed_roots`). The new arg is
optional everywhere, so existing sandbox vectors are unchanged. "Must not infer
missing context": `ingest_task_payload` requires `org_id`, `project_id`,
`run_id`, `step_id`, `executor_id`, and a non-empty `work_order.todos`; the
`REMOTE.PAYLOAD_*` validator emits findings when any are absent rather than
defaulting them.

**No Iplanic-repo dependency.** Like intake's SDD stance, we never import
Iplanic's schemas. We **vendor** the consumed payload subset and the emitted
event required-field list as version-pinned fixtures under `framework/remote/`,
and the conformance check asserts our emitted events carry exactly those required
fields. Drift is absorbed by re-pinning the mirror, not by a runtime dependency.
New decision **D-0016** records this (additive contract; transport-agnostic;
vendored mirror).

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/remote/REMOTE_EXECUTOR_CONTRACT.md` | Payload→manifest map, event mapping table, context rules, offline boundary, D-0016. |
| `framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml` | Vendored consumed-subset mirror (pinned to Iplanic source + version). |
| `framework/remote/EXECUTION-EVENT-TEMPLATE.yaml` | Vendored emitted required-field mirror. |
| `framework/conformance/rule-ids.yaml` | + `REMOTE-001` category + `REMOTE.PAYLOAD_*`; sandbox `SANDBOX.FORBIDDEN` noted in the sandbox contract. |
| `framework/effectors/SANDBOX_CONTRACT.md` | + the `forbidden_paths` arg + `SANDBOX.FORBIDDEN` reason in the contract signature. |
| `framework/conformance/remote/<name>/payload.yaml` | Input task payload. |
| `framework/conformance/remote/<name>/ledger.yaml` | Input signed ledger (for event projection). |
| `framework/conformance/remote/<name>/expect.yaml` | Expected `{manifest, events}` projection. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + contract doc, two templates, `remote_root`; `spec_version` 1.1.0. |
| `framework/VERSION` | `1.1.0`. |
| `platforms/<engine>/src/iops_<engine>/intake/payload.py` | `ingest_task_payload`. |
| `platforms/<engine>/src/iops_<engine>/validation/payload_rules.py` | `REMOTE.*` validator. |
| `platforms/<engine>/src/iops_<engine>/ledger/events.py` | `to_execution_events` (projection + sign). |
| `platforms/<engine>/src/iops_<engine>/effectors/sandbox.py` | `classify_path(..., forbidden_paths=())` + `SANDBOX.FORBIDDEN`. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | adapter wrapper `classify_path(self, path, allowed_roots, forbidden_paths=())`. |
| `platforms/<engine>/src/iops_<engine>/cli/commands.py` | `intake --payload`, `emit-events`. |
| `platforms/<engine>/{VERSION,src/iops_<engine>/__init__.py}` | engine `0.12.0` (`VERSION` + `__version__`). |
| `platforms/<engine>/FRAMEWORK_SPEC_VERSION` | `1.1.0`. |
| `platforms/<engine>/tests/test_remote.py` | payload intake, event projection, forbidden-path. |
| `framework/conformance/sandbox/forbidden/input.yaml` | new sandbox vector with `forbidden_paths` (harness extended to pass it). |
| `tests/conformance/test_sandbox.py` | thread optional `forbidden_paths` from `input.yaml`. |
| `tests/conformance/test_remote.py` | per-engine projections + differential + registry path. |

## Step Sequence

### Task 1: Framework remote-executor contract

- [ ] **Step 1:** Write `REMOTE_EXECUTOR_CONTRACT.md` — both mapping tables, the
  context rules (`forbidden_paths`, required-field list), the offline/transport
  boundary, and a worked payload→manifest→events example.
- [ ] **Step 2:** Add vendored `IPLAN-TASK-PAYLOAD-TEMPLATE.yaml` +
  `EXECUTION-EVENT-TEMPLATE.yaml` (each headed with the upstream source path +
  pinned version it mirrors).
- [ ] **Step 3:** `rule-ids.yaml` — `REMOTE-001` category + `REMOTE.PAYLOAD_*`
  (e.g. `REMOTE.PAYLOAD_IDS_MISSING`, `REMOTE.PAYLOAD_NO_TODOS`,
  `REMOTE.PAYLOAD_CONTEXT_MISSING`); bump its `spec_version`. Extend
  `framework/effectors/SANDBOX_CONTRACT.md` with the `forbidden_paths` arg +
  `SANDBOX.FORBIDDEN` reason (precedence: after the positive jail).
- [ ] **Step 4:** registry — add doc + two templates + `remote_root:
  framework/conformance/remote`.
- [ ] **Step 5:** `plans/DECISIONS.md` — add **D-0016** (additive remote-executor
  contract; vendored mirror; transport-agnostic).
- [ ] **Step 6: commit** — `feat: add Iplanic remote-executor contract (D-0016)`.

### Task 2: Conformance inputs

- [ ] **Step 1:** `remote/accept/payload.yaml` — a complete valid payload (one
  work order, two todos, `context_package` with `forbidden_paths`).
- [ ] **Step 2:** `remote/accept/ledger.yaml` — a small signed run ledger using
  the **real** event_types (`task_started` → `file_edited` → `commit`) with the
  task reaching `status: completed` and `acceptance.result: pass`, so the
  projection exercises both directly-mapped log events
  (`task_started`/`file_edited`/`task_completed`/`commit`) and the derived
  `test.passed`.
- [ ] **Step 3:** `remote/reject_context/payload.yaml` — a payload missing
  `executor_id` + empty `todos` (drives `REMOTE.PAYLOAD_*`).
- [ ] **Step 4: commit** — `test: add remote-executor conformance inputs`.
  (`expect.yaml` is regenerated from the engine in Task 3, per the
  PLAN-005/009/011 pattern.)

### Task 3: Hermes implementation (TDD)

- [ ] **Step 1: failing tests** — `ingest_task_payload` maps the accept payload
  to the expected manifest (ids preserved in `remote_execution`); the run loop
  accepts that manifest unchanged; `payload_rules` flags the reject payload;
  `to_execution_events` projects the ledger to schema-shaped, signed events from
  log events (`task_started`/`file_edited`/`task_completed`/`commit`) mapped
  directly **plus** derived `test.passed`/`test.failed` read from the task
  entry's `acceptance.result` — with `agent_id` dropped, `executor_id` used, and
  `compensation`/`resolution` skipped; `classify_path` returns
  `SANDBOX.FORBIDDEN` for a forbidden path and still `ESCAPE`/`OUTSIDE_ROOTS`
  for those. Fail first.
- [ ] **Step 2:** implement `intake/payload.py`, `validation/payload_rules.py`,
  `ledger/events.py` (signature prefix-split → `{key_id, algorithm, value}`,
  exactly three keys), the `sandbox.py` extension, **and** the
  `engine.py` adapter wrapper `classify_path(self, path, allowed_roots,
  forbidden_paths=())`.
- [ ] **Step 3:** `cli/commands.py` — `intake --payload <file>` (emit manifest)
  and `emit-events <ledger> --payload <file> [--key-env IOPS_SIGNING_KEY]`.
- [ ] **Step 4: (re)generate** `remote/*/expect.yaml` from the engine.
- [ ] **Step 5: green** — `pytest`, `ruff`, `mypy --strict`. Commit
  `feat: add Iplanic payload intake + event projection to hermes`.

### Task 4: Claude implementation (independent copy)

- [ ] **Step 1–4:** mirror Task 3 as an independent copy — **no import of
  `iplan_hermes`**; identical behavior.
- [ ] **Step 5: green** + commit `feat: add Iplanic payload intake + event
  projection to claude`.

### Task 5: Conformance

- [ ] **Step 1:** `tests/conformance/test_remote.py` — for each `remote/`
  sample × engine: assert `ingest_task_payload` projection equals
  `expect.manifest`; assert `to_execution_events` (fixed key + injected ids)
  equals `expect.events` **and** every emitted event carries exactly the
  `EXECUTION-EVENT-TEMPLATE.yaml` required fields (`signature` exactly its three
  keys); assert engines produce identical manifests **and** identical events
  (differential). Extend `test_registry` to `remote_root`.
- [ ] **Step 2:** reach `SANDBOX.FORBIDDEN` through the **existing** sandbox
  harness: add `framework/conformance/sandbox/forbidden/input.yaml` (a `path`
  inside `allowed_roots` but under a `forbidden_paths` entry), and thread an
  optional `forbidden_paths` through `tests/conformance/test_sandbox.py:29` and
  the `engine.py` adapter wrapper so both engines agree. Existing sandbox vectors
  (no `forbidden_paths`) are unchanged.
- [ ] **Step 3: full suite** + commit `test: add remote-executor + forbidden-path
  conformance`.

### Task 6: Version bump, changelog, handoff

- [ ] **Step 1:** atomic bump. **Spec (gated):** `framework/VERSION` 1.1.0,
  registry `spec_version` 1.1.0 (`test_registry.py`), both engines'
  `FRAMEWORK_SPEC_VERSION` 1.1.0 (`test_engines.py`). **Engine stream
  (convention):** each engine `VERSION` **and** `src/iops_<engine>/__init__.py`
  `__version__` 0.11.0 → 0.12.0 (they must stay equal). **Note:** each
  `platforms/<engine>/pyproject.toml` `version` is already `1.0.0` (a
  pre-existing divergence from the `VERSION`/`__version__` 0.11.x stream); it is
  not gated and **out of scope** to reconcile here — leave it, don't "fix" it
  silently.
- [ ] **Step 2:** `CHANGELOG.md` `[1.1.0]`; `ROADMAP.md` (new Phase 13 row,
  status done); `README.md` capability line; `HANDOFF.md` (PLAN-013 DONE,
  blocker resolved); `TODO.md` (check off PLAN-013, move live transport to
  deferred). Mark this plan `DONE`.
- [ ] **Step 3: full verification** + commit `chore: release spec v1.1.0
  (Iplanic remote-executor conformance)`.

## Verification

> Nothing is "done" until these pass.

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
pre-commit run --all-files
```

Expected:

1. Conformance green: payload→manifest and ledger→events projections match
   `expect` per engine; engines produce **identical** manifests + events
   (differential, no normalization); emitted events carry exactly the vendored
   required fields; `SANDBOX.FORBIDDEN` agrees across engines; all prior checks
   unchanged at spec `1.1.0`.
2. Per-engine tests: accept payload → valid manifest the run loop ingests;
   reject payload → `REMOTE.PAYLOAD_*`; events signed + schema-shaped with
   engine `agent_id` absent and payload `executor_id` present; forbidden path
   denied while `allowed_roots` paths still pass.
3. `ruff` + `mypy --strict` clean (CI installs `[dev]` only; the `yaml`
   `type: ignore` stays needed there).
4. Standalone path unchanged: existing `ingest_iplan`, run, gate, chain,
   signing, and sandbox tests/vectors all still pass.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Payload intake forks the run loop. | It produces the **same `iplan-intake` manifest**; the loop/gate/saga/evidence are untouched. Extra `remote_execution`/`forbidden_paths` keys are ignored by the loop (additive). |
| R2 | Engine `agent_id` in events breaks the differential. | `to_execution_events` **drops** `agent_id` and uses the payload `executor_id` + injected ids; events are engine-identity-free → no normalization (PLAN-011 R2 pattern). |
| R3 | Hard dependency on the (private) Iplanic repo. | No import: the consumed subset + emitted required-field list are **vendored, version-pinned** mirrors under `framework/remote/` (the intake "no SDD dependency" stance). Drift = re-pin the mirror. |
| R4 | "Signed log-ingestion" implies live HTTP. | Out of scope: emission is offline/in-memory; the POST is integration-only behind an extra (PLAN-008 live-executor pattern). The shape + signature are what's proven here. |
| R5 | `forbidden_paths` change weakens the existing sandbox. | New param defaults to `()` (no behavior change for current callers: `effectors/apply.py`, host-runtime); `SANDBOX.FORBIDDEN` checked **after** the positive jail so `ESCAPE`/`OUTSIDE_ROOTS` precedence holds. Reaching it through conformance also requires the `engine.py` adapter wrapper + sandbox harness/`input.yaml` to thread the optional arg (in scope); existing sandbox vectors stay unchanged. |
| R6 | Approval is asserted, not measured, in payload mode. | Documented decision: Iplanic owns the `EXEC-Ready ≥90` gate and only dispatches approved work, so dispatch **is** the approval; the standalone `ingest_iplan` path still measures the score. Captured in D-0016 + the contract. |
| R7 | Non-determinism across engine event emission. | One injected `ids` source + ledger timestamps; `received_at = occurred_at` offline; both engines (copies) emit identical events (R-pattern). |
| R8 | Spec-version bump scope. | Additive, backward-compatible → MINOR (`1.1.0`); the conformance suite is the gate (CONTRIBUTING). Registry + both `FRAMEWORK_SPEC_VERSION` bump atomically with `framework/VERSION`. |

## Claim ledger

> Load-bearing **in-repo** claims, each citing the `file:line` verified this
> session. Cross-repo Iplanic-contract claims (sibling `iplanic` repo) are
> outside the gate's reach — it resolves citations relative to *this* repo's root
> — and were hand-verified against the vendored mirrors, per the plan's
> "no Iplanic-repo dependency" stance.

| # | Claim | Symbol | Citation |
|---|-------|--------|----------|
| 1 | `task_completed` IS an appended execution_log event (maps directly to Iplanic `task.completed`) | `task_completed` | platforms/hermes/src/iplan_hermes/orchestrator/loop.py:223 |
| 2 | acceptance outcome is set on the task entry, not a log event (so `test.*` are derived) | `acceptance` | platforms/hermes/src/iplan_hermes/orchestrator/loop.py:219 |
| 3 | the engine sandbox wrapper takes `(path, allowed_roots)` — must thread `forbidden_paths` | `classify_path` | platforms/hermes/src/iplan_hermes/engine.py:97 |
| 4 | the legacy `sign_event` HMACs IOPS's own canonical form — retained for the standalone ledger, **not** used for Iplanic emission (PLAN-014 replaces it) | `sign_event` | platforms/hermes/src/iplan_hermes/security/signing.py:21 |
| 9 | IOPS `_canonical` is `json.dumps(sort_keys)` excluding only `signature` — not RFC 8785 JCS, no drop-null, and it signs `received_at`: the conformance gap PLAN-014 closes | `_canonical` | platforms/hermes/src/iplan_hermes/security/signing.py:13 |
| 5 | `ingest_iplan` emits an `iplan-intake` manifest (payload-mode reuses this shape) | `iplan-intake` | platforms/hermes/src/iplan_hermes/intake/reader.py:41 |
| 6 | intake scope validation requires `client_id`/`project_id`/`allowed_roots` | `allowed_roots` | platforms/hermes/src/iplan_hermes/validation/intake_rules.py:33 |
| 7 | next decision number is D-0016 (highest existing decision is D-0015; sections are not in file order) | `D-0015` | plans/DECISIONS.md:251 |
| 8 | real `execution_log` event_types: task_started / file_edited / task_completed / task_blocked / commit / compensation | `file_edited` | platforms/hermes/src/iplan_hermes/orchestrator/loop.py:214 |

## Review log

> ≥2 passes before implementation. Each pass: re-read the whole plan, list
> findings, fold fixes back into the sections above. Stop when a pass finds
> nothing. At least one pass MUST be an independent fresh-context review.
> **If a pass produces findings beyond the original gap count, treat the surplus
> as speculative scope and cut it.**

### Pass 1 - 2026-06-07

- Finding: original draft included emitting `executor-registration` to Iplanic
  as a fourth runtime capability. That is **not** in the handoff's a/b/c/d and is
  speculative for a "be dispatchable" plan → **cut to Out #2** (static
  understanding only). Keeps the plan at the 3 real gaps + conformance.
- Finding: the draft was ambiguous on approval. The Iplanic payload carries no
  `exec_ready_score`; re-deriving one would be inventing context. Resolved:
  **dispatch is the approval** (Iplanic owns the gate) — folded into the mapping
  table, R6, and D-0016. The standalone path keeps measuring the score.
- Finding: `received_at` is required by the event schema but is genuinely
  Iplanic's to stamp on ingest. For offline determinism, set `received_at =
  occurred_at` and document that Iplanic overwrites it — folded into Approach +
  R7 (avoids a clock dependency that would break the differential).
- Finding: a live HTTP POST would pull in transport, retries, and auth — scope
  blowup. Pinned the boundary: **emit in-memory; transport is integration-only**
  (Out #1, R4), mirroring how PLAN-008 kept real clients out of CI.

### Pass 2 - 2026-06-07

- Finding: adding `forbidden_paths` to `classify_path` could change behavior for
  existing callers and risk weakening a conformance check. Confirmed safe — new
  param defaults to `()`, checked after the positive jail; existing sandbox
  vectors are unchanged and a new forbidden vector is added (R5). No existing
  check is weakened (D-0011/CONTRIBUTING).
- Finding: event-type mapping could silently guess for unmapped engine event
  kinds. Made the mapping **explicit and total** over the kinds IOPS records;
  unmapped kinds are skipped, not invented (Approach).
- Finding: vendored mirrors could rot silently against Iplanic. Accepted as the
  correct trade (the intake/SDD precedent): the mirror is version-pinned and the
  conformance check asserts emitted events match exactly the mirrored required
  fields, so a drift surfaces as a failing vector when the mirror is re-pinned —
  not as a hidden runtime coupling (R3).
- Scope check: findings this pass are clarifications within the 3-gap problem,
  not new scope.

### Pass 3 - 2026-06-07 (verification against the live ledger — partial, corrected by Pass 4)

- Finding: the Pass-1 event table used idealized event names. Reading
  `orchestrator/loop.py` flagged a mismatch and prompted a rewrite. **This pass
  drew a partly-wrong conclusion** — it claimed `task_completed` is *not* a log
  event (the read stopped before `loop.py:223`). Pass 4 (independent review)
  corrected this. Recorded here honestly rather than silently overwritten.
- Finding (correct): `test.passed`/`test.failed` have no log event — the
  acceptance outcome is set on the task entry (`loop.py:219`) — so they must be
  derived. That half stands.

### Pass 4 - 2026-06-07 (independent adversarial review vs. source + contracts)

An independent reviewer re-read the plan against the live engine code, the
conformance harness, and the Iplanic contracts. Findings (all verified against
`file:line` before folding in):

- **BLOCKER — event table wrong (corrects Pass 3).** `task_completed` *is* an
  appended `execution_log` event (`loop.py:223`), and `compensation`
  (`loop.py:228`) is a real event the table omitted. Rewrote the mapping:
  `task_started`/`file_edited`/`task_completed`/`task_blocked`/`commit` map
  **directly** from log events; only `test.passed`/`test.failed` are derived
  (from `acceptance.result`); `compensation` + `resolution` are explicit,
  documented skips. Updated Approach, Task 2, Task 3.
- **BLOCKER — `SANDBOX.FORBIDDEN` was unreachable.** The engine adapter wrapper
  `EngineProtocol.classify_path(self, path, allowed_roots)` (`engine.py:97`) and
  the sandbox harness (`test_sandbox.py:29` + `sandbox/*/input.yaml`) carry no
  `forbidden_paths`, so a new vector couldn't drive the reason. Added the adapter
  wrapper (both engines), `framework/effectors/SANDBOX_CONTRACT.md`, and the
  harness/`input.yaml` thread to scope (File Structure, Task 1/3/5, R5).
- **SHOULD-FIX — version markers incomplete.** Added `__init__.__version__` to
  the engine bump and recorded the pre-existing `pyproject.toml version = 1.0.0`
  vs `VERSION = 0.11.0` divergence as out-of-scope, not silently "fixed"
  (Scope #6, Task 6 Step 1).
- **SHOULD-FIX — signature prefix.** `sign_event` returns `"hmac-sha256:<hex>"`;
  the projection must split on `:` to fill `signature.value`, emitting exactly
  the three schema-allowed keys (`additionalProperties: false`). Stated in
  Approach + Task 3 Step 2.
- Confirmed-correct (no change): extra manifest keys are ignored by
  `intake_rules`/`ledger_rules` (R1); `approved=true`+score 90 clears
  `INTAKE.APPROVAL_INSUFFICIENT` (R6); the `remote/` checked-in `expect.yaml`
  follows the **signing** vector precedent; D-0016 is the right next number;
  cutting executor-registration (Out #2) is correctly sized.
- Scope unchanged — every fix is a correction within the 3 gaps + conformance,
  no new features. The two BLOCKERs were load-bearing technical errors a true
  independent pass caught that authoring-time passes did not; the plan is now
  consistent across Approach / File Structure / Steps / Verification / Risks and
  is ready for approval.

### Pass 5 - 2026-06-07 - independent (final, after adding the Claim ledger)

A fresh-context reviewer verified all 8 Claim-ledger rows against source — **8/8
TRUE** (citation resolves, symbol present, *and* claim accurate) — confirmed no
in-repo load-bearing claim is missing, and traced the 3 gaps (payload intake,
event projection, forbidden_paths sandbox) soundly against the cited code. It
raised two cosmetic NITs (row-7 wording "ends at D-0015" vs. file order; the
claude wrapper is `engine.py:102` not `:97`), both fixed. **No further findings**
— no load-bearing issues remain. Plan is ready.

### Pass 6 - 2026-06-11 - re-grounding against the frozen Iplanic standard

Iplanic's IPLAN standard was frozen after this plan was written (Iplanic
PLAN-001…008 / D-0021…D-0028). Re-reading the plan against the now-normative
contracts surfaced **one load-bearing correction** (the rest of the plan holds):

- **[load-bearing] Signing did not match Iplanic.** The Approach reused
  `security.signing.sign_event` — HMAC over IOPS's own `json.dumps(sort_keys)`
  canonical, excluding only `signature` and **including `received_at`**. Iplanic's
  frozen `iplan-canonical-json` is RFC 8785 JCS + `sha256` with recursive drop-null
  and a signed payload excluding `{signature, received_at}`, keyed with raw bytes,
  supporting `ed25519` too. Proven non-matching against Iplanic's golden `sig_hmac`
  vector (`7ce5… ≠ bcac…`); and because IOPS signs `received_at`, which Iplanic
  overwrites at ingest, the signature would fail verification. → **Folded in:**
  Re-grounding §1 splits the canonical signer into the focused **PLAN-014**;
  Approach now consumes it instead of `sign_event`; Claim ledger rows 4/9 record the
  legacy signer's retained-but-unused role and the divergence.
- **[load-bearing] Conformance asserted field-presence, not byte-reproduction.**
  Iplanic now publishes golden vectors (`canonicalization`, `status_projection`,
  `scope_check`). → Re-grounding §2: the suite vendors and reproduces them; mirrors
  re-pin to `schema_version 1.2-draft`.
- Confirmed **already-aligned** (no change): the event-type→status mapping matches
  Iplanic's published Status Projection; `received_at = occurred_at` offline is
  admitted by the Clock-Skew Window (skew 0); tenant fields (`org_id`/`project_id`/
  `executor_id`) populate the scope-check inputs.

A fresh-context independent pass on this re-grounding ran paired with PLAN-014
(2026-06-11): it confirmed the signing divergence by **running the differential**
(`7ce5… ≠ bcac…`), verified PLAN-013 rows 4/9 resolve, and confirmed the corrected
Approach consumes PLAN-014's canonical signer (which it independently verified
reproduces Iplanic's golden vectors). No load-bearing issues in the re-grounding;
the only fix landed in PLAN-014 (its `sign` return type).

**Result:** ready (re-grounded; signing consumes PLAN-014).
