# D-4b — Iplanic Transport Implementation Plan

> Development plans follow the SDD workflow inherited from
> `aidoc-flow-framework`: **plan → review (≥2 passes) → implement → verify →
> land**. ≥2 review passes recorded in `## Review log`, ≥1 independent
> fresh-context, before implementation; harden until a pass finds nothing.
>
> **Size to the problem.** This builds the transport designed in PLAN-017 /
> D-0020 — no new design surface.

**Goal:** Build the **ledger-relay / drain worker** that streams the local signed
execution ledger to iplanic `POST /v1/events`, gated by a config **sync toggle
(off by default)**, with a durable cursor + dead-letter, the reject→outcome map,
a bearer-token seam, and an on-demand `sync` CLI command — plus the load-bearing
**idempotency-key fix** (anchor on the hash-chain identity). Per-engine
(`hermes` + `claude`), parity proven by vectors. Implements the ratified design
in `plans/PLAN-017` + D-0020.

**Architecture:** New per-engine `relay/` package consuming the existing durable
ledger (`ledger/persistence.py`) + projection (`ledger/events.py:to_execution_events`)
+ signer (`security/iplanic_signing.py`). No `framework/` contract change (the
wire event shape is unchanged); the idempotency-key fix is a **value-derivation**
change that regenerates the projection golden. Standalone runs are unaffected —
sync is opt-in.

**Tech Stack:** Python ≥3.11 (`urllib`/stdlib HTTP — no new deps), `unittest`/`pytest`.

---

| Field      | Value |
|------------|-------|
| Task       | D-4b (build of D-4 transport) |
| Depends on | `plans/PLAN-017` (design, DONE) + D-0020; D-0016/D-0018 (contract); D-0011 (isolation) |
| Status     | DONE - 2026-06-15 |
| Feeds      | The "online (with iplanic)" + on-demand-sync operating modes (README / TODO / ROADMAP) |

## Objective

iplan-runner is already a conformant iplanic remote executor that *projects + signs*
its ledger into iplanic `execution-event`s offline. D-4b adds the **transport**:
a per-engine drain worker that delivers those events to iplanic over HTTP, with
durable at-least-once semantics, gated by a config toggle so standalone/offline
stays the default. This makes the documented "online" + "on-demand sync" modes
real.

## Scope

**In:**

1. **Idempotency-key fix (prerequisite).** Derive `event_id` + `idempotency_key`
   + `trace_id` from the D-0008 hash-chain identity (`event_hash`) instead of the
   positional `IdSource` counter, so re-projection is byte-stable and iplanic's
   dedup works. **A single `task_completed` log event fans out to two projected
   events** (`task.completed` + `test.passed`/`test.failed`, same `event_hash`),
   so the derivation MUST include an `event_type` discriminator (e.g.
   `{run_id}:{event_hash}:{event_type}`) — a bare `event_hash` collides and iplanic
   would drop the second as a replay. Regenerate the projection golden
   `expect.yaml`, including its `signature.value`s (id/key/trace_id are inside the
   signed payload).
1a. **Persist the iplanic identity at run time.** `to_execution_events` needs the
   8 identity fields from the iplanic **payload**, but the durable store holds only
   the ledger — so the drain worker/`sync` (a separate invocation) has no identity
   to project with. Persist the payload's identity block into the store at
   payload-mode run/intake time (sidecar, next to the ledger); `sync` loads it.
2. **Per-engine `relay/` package:** transport client (HTTP `POST /v1/events`,
   bounded retry/backoff, injected bearer-token provider seam), drain worker
   (read durable ledger in append order → project → sign → POST verbatim → on
   `202` advance cursor), durable cursor + dead-letter store.
3. **Reject → outcome map** (the classifier from PLAN-017): `202`→advance;
   `timestamp_skew`→local heuristic (far-stale→dead-letter, else retry-cap);
   `invalid_signature`/`schema_invalid`→halt; registration/scope (403)→dead-letter;
   `401`→refresh-once→escalate; transport/5xx→retry-backoff.
4. **Config:** an `iplanic` sync block (`sync.enabled` **default false**,
   endpoint, auth token from env) on `Config`.
5. **CLI:** an on-demand `sync` command (drain from the durable cursor).
6. **Gated integration suite (not in CI):** in-process fake iplanic `/v1/events`
   server, opt-in (PLAN-008 pattern), per engine — asserts 202+idempotent replay,
   each reject→outcome, dead-letter-doesn't-stall, auth-refresh-once.
7. Both engines (`hermes`, `claude`), no shared code; parity via the suite.

**Out:**

1. Real OIDC/SPIFFE auth — only the bearer-token **seam** (static token in tests);
   full wiring stays D-0015.
2. Any wire-shape / `framework/` contract change (only the `event_id`/
   `idempotency_key` value-derivation changes).
3. iplanic-side anything; `run_chain` rework; TMP-IPLAN.
3a. Attaching an iplanic identity to a run that never had one (a pure-SDD
   standalone run has no org/project/iplan identity → nothing to project to
   iplanic). `sync` requires a persisted (or config-supplied) identity and errors
   clearly otherwise; synthesizing/registering identity for an identity-less run
   is a later item.
4. A long-running daemon/auto-sync — sync is on-demand (`sync` command / toggle);
   continuous-relay scheduling is a later item if needed.

## Approach

The drain worker is a thin, durable loop over the existing pieces. Read the
verified ledger (`ledger/persistence.py:load`), project to events
(`ledger/events.py:to_execution_events`), and for each event past the cursor:
sign (already done in projection), POST verbatim to `<endpoint>/v1/events`,
classify the response, and either advance the cursor (`202`) or route to the
durable dead-letter — **cursor advances past a terminal reject only after a
durable dead-letter commit** (no silent loss). The cursor + dead-letter persist
next to the ledger store (extend the `ledger/index.py` control-file pattern).

The **idempotency-key fix** is the one change that touches existing code +
goldens: `_build_event` (`ledger/events.py:50,55`) currently derives `event_id`
from the positional `IdSource` (`ids("EV")`) and `idempotency_key` as
`{run_id}:{event_id}`. Re-projection yields fresh ordinals → iplanic can't dedup.
D-4b anchors both on the hash-chain `event_hash` (stable + tamper-evident). The
wire fields are unchanged; only their values change, so the projection golden
`framework/conformance/remote/accept/expect.yaml` is regenerated and the
cross-engine conformance re-proven. The iplanic signing vectors
(`framework/remote/iplanic-vectors/`) sign *given* events and are unaffected.

Per D-0011 strict isolation, everything is implemented twice (hermes + claude,
byte-parallel) with parity proven by the conformance suite + the fake-server
integration suite run against both.

## File Structure

| Path | Responsibility |
|------|----------------|
| `platforms/<engine>/src/iplan_<engine>/ledger/events.py` | Modify `_build_event`: anchor `event_id`/`idempotency_key` on `event_hash` |
| `platforms/<engine>/src/iplan_<engine>/relay/client.py` | HTTP `POST /v1/events`, bearer-token provider seam, bounded retry/backoff, `deliver(event) -> Outcome` |
| `platforms/<engine>/src/iplan_<engine>/relay/worker.py` | Drain loop: read ledger → project → POST → advance cursor / dead-letter |
| `platforms/<engine>/src/iplan_<engine>/relay/store.py` | Durable cursor + dead-letter (extends the `ledger/index.py` control pattern) |
| `platforms/<engine>/src/iplan_<engine>/relay/reject.py` | Reject-code → outcome classifier (incl. local `timestamp_skew` heuristic) |
| `platforms/<engine>/src/iplan_<engine>/config.py` | Add the `iplanic` sync block to `Config` + `load_config` |
| `platforms/<engine>/src/iplan_<engine>/cli/commands.py` | Add the on-demand `sync` subcommand |
| `platforms/<engine>/tests/test_iplanic_transport.py` | Gated fake-server integration suite (opt-in, not in CI) |
| `framework/conformance/remote/accept/expect.yaml` | Regenerated projection golden (new `event_id`/`idempotency_key` values) |

## Step Sequence

### Task 1: Idempotency-key fix + golden regen (both engines)

- [ ] **Step 1:** In each engine's `ledger/events.py:_build_event`, thread the
  source `log_event`'s `event_hash` in and derive: `idempotency_key =
  {run_id}:{event_hash}:{event_type}` (the `event_type` discriminator avoids the
  fan-out collision — one `event_hash` → `task.completed` + `test.*`),
  `event_id = EV-<short-hash-of-that-key>`, and `trace_id` likewise anchored on
  `event_hash` (not the positional `ids("TR")`). The wire fields are unchanged;
  only their values are now content-stable.
- [ ] **Step 2:** Regenerate `framework/conformance/remote/accept/expect.yaml` —
  the new `event_id`/`idempotency_key`/`trace_id` **and** the `signature.value`s
  (those fields are inside `signing_payload`). Run the remote conformance +
  cross-engine differential until green. (The `framework/remote/iplanic-vectors/`
  signing vectors sign a fixed given event and are NOT regenerated.)
- [ ] **Step 3: Commit** `fix(ledger): anchor execution-event id/idempotency_key on hash-chain identity (D-4b)`

### Task 2: Per-engine relay package (client / worker / store / reject)

- [ ] **Step 1:** `relay/client.py` — stdlib HTTP POST to `<endpoint>/v1/events`,
  bearer token from an injected provider (static in tests), bounded
  retry/backoff on transport/5xx; returns a typed `Outcome`.
- [ ] **Step 2:** `relay/store.py` — durable cursor keyed on the **projected-event
  identity** (the stable `idempotency_key`), NOT the raw log `sequence` —
  projection skips some log kinds and fans `task_completed` out to two events, so
  a log-sequence cursor is not 1:1 with emitted events. Plus a durable dead-letter
  sink next to the ledger store; write-order: dead-letter commit **before** cursor
  advance.
- [ ] **Step 2a:** Persist the iplanic identity block at payload-mode run/intake
  time (sidecar next to the ledger); the worker + `sync` load `ledger + identity`
  to project. `sync` errors clearly if no identity is persisted or configured.
- [ ] **Step 3:** `relay/reject.py` — the reject→outcome map incl. the local
  `timestamp_skew` heuristic (`MAX_AGE` default 86400s).
- [ ] **Step 4:** `relay/worker.py` — drain loop tying the above to
  `persistence.load` + `to_execution_events`.
- [ ] **Step 5: Commit** (per engine) `feat(relay): iplanic transport drain worker + durable cursor/dead-letter`

### Task 3: Config toggle + CLI `sync` command

- [ ] **Step 1:** Add the `iplanic` sync block to `Config`/`load_config`
  (`sync.enabled` default **false**; endpoint; token via env, never file).
- [ ] **Step 2:** Add the `sync` subcommand (drain from the cursor; `--store`,
  `--dry-run`); no-op with a clear message when `sync.enabled` is false.
- [ ] **Step 3: Commit** `feat(cli): on-demand iplanic sync command + config toggle (off by default)`

### Task 4: Gated fake-server integration suite (both engines)

- [ ] **Step 1:** `tests/test_iplanic_transport.py` (per engine) — in-process fake
  `/v1/events` server (202 + reject envelopes from the vendored vectors), opt-in
  marker / skip-without-flag (PLAN-008 pattern, not in CI). Assert: 202 + idempotent
  replay, each reject→outcome, dead-letter-doesn't-stall, auth-refresh-once.
- [ ] **Step 2: Commit** `test(relay): gated fake-iplanic integration suite (per engine)`

### Task 5: Docs

- [ ] **Step 1:** `CHANGELOG.md` `[Unreleased]`; refresh `plans/HANDOFF.md`
  (D-4b built), `TODO.md` (check off the operating-modes items), mark this plan
  `Status: DONE`.

## Verification

> Nothing is "done" until these pass.

```bash
# conformance + cross-engine parity (incl. regenerated projection golden)
python -m unittest discover -s tests/conformance
# engine unit/integration (offline)
pytest platforms/hermes platforms/claude -q
# lint + types
ruff check platforms && mypy --strict platforms/hermes/src platforms/claude/src
# the gated transport suite (opt-in; not in CI)
IPLAN_FAKE_IPLANIC=1 pytest platforms/hermes/tests/test_iplanic_transport.py platforms/claude/tests/test_iplanic_transport.py -q
# standalone unaffected: a run with sync disabled never opens a socket
iplan-hermes run examples/IPLAN-EXAMPLE.yaml --store /tmp/s && iplan-hermes sync --store /tmp/s   # prints "sync disabled"
```

Expected: conformance + parity green with the new idempotency values; the fake-server
suite proves 202/idempotency + every reject→outcome + dead-letter durability + auth
refresh on both engines; a sync-disabled run makes no network call.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Idempotency-key change silently breaks dedup or vectors | Task 1 regenerates the projection golden + cross-engine differential; the fake-server suite asserts idempotent replay |
| R2 | Engine drift (hermes vs claude relay diverge) | Per-engine but parity-tested by the same suite + golden vectors (D-0011/D-0012) |
| R3 | Cursor advances past a lost event (silent data loss) | Write-order invariant: durable dead-letter commit **before** cursor advance; covered by a suite case |
| R4 | Sync accidentally on by default → unexpected egress | `sync.enabled` defaults **false**; `sync` no-ops + says so when disabled; a test asserts no socket on a standalone run |
| R5 | Real network/credentials needed in CI | Fake in-process server + injected static token; suite is opt-in, never in CI (PLAN-008 pattern) |
| R6 | id/key collision drops the second of two events sharing one `event_hash` | Derivation includes the `event_type` discriminator (Task 1 Step 1); the fake-server suite asserts both `task.completed` + `test.*` are accepted, not deduped |
| R7 | Worker can't project — no identity in the store | Task 2a persists the payload identity at run time; `sync` loads ledger + identity and errors clearly when absent |

## Claim ledger

> Every load-bearing claim cites the `file:line` actually read.

| # | Claim | Symbol | Citation |
|---|-------|--------|----------|
| 1 | Hash-chain identity = the stable anchor for idempotency | `def compute_event_hash` | platforms/hermes/src/iplan_hermes/ledger/store.py:12 |
| 2 | `event_id` is now derived from the hash-chain identity (was a positional counter) | `event_id = "EV-"` | platforms/hermes/src/iplan_hermes/ledger/events.py:28 |
| 3 | `idempotency_key` is now `{run_id}:{event_hash}:{event_type}` (content-stable) | `idem = f"{run_id}` | platforms/hermes/src/iplan_hermes/ledger/events.py:27 |
| 4 | Projection entry point the worker consumes | `def to_execution_events` | platforms/hermes/src/iplan_hermes/ledger/events.py:84 |
| 5 | Events are signed (canonical-JSON) before send | `def sign` | platforms/hermes/src/iplan_hermes/security/iplan_canonical/signing.py:37 |
| 6 | Signed form excludes `received_at`/`signature` | `def signing_payload` | platforms/hermes/src/iplan_hermes/security/iplan_canonical/signing.py:25 |
| 7 | `Config` is the slot for the sync toggle | `class Config` | platforms/hermes/src/iplan_hermes/config.py:21 |
| 8 | The projection golden pins `event_id`/`idempotency_key` (regenerated, hash-anchored) | `event_id: EV-` | framework/conformance/remote/accept/expect.yaml:51 |
| 9 | iplanic `1.3-draft` required event fields (wire shape unchanged) | `required:` | framework/remote/EXECUTION-EVENT-TEMPLATE.yaml:13 |
| 10 | D-0020 ratifies the relay/at-least-once/dead-letter design | `### D-0020` | plans/DECISIONS.md:196 |
| 11 | D-0011 strict engine isolation (implement per-engine) | `### D-0011` | plans/DECISIONS.md:100 |
| 12 | Gated, not-in-CI integration pattern to mirror | `opt-in, keyed, not in CI` | plans/PLAN-008_config-live-executors.md:21 |
| 13 | The design this builds (drain worker, reject map, dead-letter) | `D-4` | plans/PLAN-017_d4-iplanic-transport-design.md:1 |
| 14 | One `task_completed` log event fans out to two projected events (id/key must discriminate) | `test.passed` | platforms/hermes/src/iplan_hermes/ledger/events.py:117 |
| 15 | Projection identity comes from the payload, not the ledger (worker must persist it) | `payload.get` | platforms/hermes/src/iplan_hermes/ledger/events.py:91 |

## Review log

> ≥2 passes before implementation; ≥1 independent fresh-context review.

### Pass 1 - 2026-06-15 - author self-review

- Drafted from the two Explore sweeps; confirmed citation anchors by grep
  (store.py:12, events.py:50/55/68, iplanic_signing.py:55/64, config.py:21,
  accept/expect.yaml:51). Sized to D-4b — no speculative scope beyond the
  PLAN-017/D-0020 design. Flagged the golden-regen as in-scope (the idempotency
  change alters projected values).

### Pass 2 - 2026-06-15 - independent (general-purpose Agent, fresh context)

All 13 original citations verified accurate. Two **[BLOCKING]** design gaps + two
[SHOULD] found and folded:

- **[BLOCKING] id/key collision.** One `task_completed` log event projects to two
  events (`task.completed` + `test.passed`/`test.failed`, same `event_hash`), so a
  bare-`event_hash` key collides → iplanic drops the second. **Fixed:** derivation
  now includes an `event_type` discriminator (Scope 1 / Task 1 Step 1; R6;
  ledger 14).
- **[BLOCKING] no identity source.** `to_execution_events` pulls the 8 identity
  fields from the payload, but the store holds only the ledger → the drain worker
  has nothing to project. **Fixed:** persist the payload identity at run time;
  `sync` loads ledger + identity (Scope 1a; Task 2a; Out 3a; R7; ledger 15).
- **[SHOULD] `trace_id` left positional** → re-projection signature drift.
  **Fixed:** anchor `trace_id` on `event_hash` too (Task 1 Step 1).
- **[SHOULD] golden regen** must include `signature.value`s (id/key/trace are in
  the signed payload). **Fixed:** Task 1 Step 2 says so.
- [NIT] cursor must key on projected-event identity, not raw log sequence (skips +
  fan-out). **Fixed:** Task 2 Step 2.

### Pass 3 - 2026-06-15 - independent (general-purpose Agent, fresh context) - confirmation

Reviewer verified against source: **both blocking fixes resolved.** (1) The
`event_type` discriminator uniquely disambiguates the only fan-out
(`task.completed` + `test.*` from one `event_hash`; the two `events.append` sites
at `events.py:84,98` are the sole fan-out; every other kind emits one event). (2)
`to_execution_events` needs only `(ledger, identity, key/key_id)` — persisting the
8-field identity at run time is sufficient for a separate `sync` to re-project;
`key_id` defaults to `payload.executor_id` which is inside that block. `trace_id`
anchoring, signature regen, and the membership-style projected-`idempotency_key`
cursor are all coherent with the code. Ledger rows 14/15 + spot-checked rows
accurate; engines byte-identical. No new gaps.

**Result: ready** — no further load-bearing findings.
