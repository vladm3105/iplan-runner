# PLAN-017 — D-4 Iplanic transport design (ledger-relay → `POST /v1/events`)

> **Phase D capstone, plan 4 of 4 — DESIGN / SPEC / ADR ONLY.** This plan produces the
> **design specification + architecture decision** for D-4: the iplan-runner-side
> **transport** that delivers this executor's signed `execution-event`s to Iplanic's
> ingestion endpoint. It ships **no source code, no HTTP client, no tests** — those are a
> later build-stage plan (D-4b). The deliverable is documentation: the relay/worker
> design, the transport-client + auth seams, the retry/at-least-once policy, the
> reject-code → outcome map, the integration-test strategy, and the proposed decision
> **D-0020**.

## What exists vs. what D-4 is

iplan-runner is **already a conformant Iplanic remote executor** (D-0016,
`REMOTE_EXECUTOR_CONTRACT.md`): it emits **signed `execution-event`s in Iplanic's shape
by projecting its own signed ledger** — the projection (`to_execution_events`) and the
byte-reproducible signer (`iplanic_signing.sign`) are **done and conformance-proven**
(PLAN-013/014/015). D-0016 was deliberately **transport-agnostic** — it defined *what*
to emit, not *how to deliver it*. **D-4 fills that transport gap**: take the projected,
signed events and actually **`POST` them to Iplanic's `/v1/events`**, with auth, retry,
and response handling. No event-shape/signing work — that contract is frozen.

## The Iplanic contract D-4 conforms to (cross-repo, narrative)

The sibling `iplanic` service exposes `POST /v1/events` (D-1/D-2): a valid signed event
returns **`202 {event_id}`** (also on idempotent replay — a duplicate `idempotency_key`
returns the original `event_id`); a rejected event returns **`{reason, detail}`** at a
mapped HTTP status — `401 unauthenticated`; `403` for `unregistered_executor` /
`executor_not_active` / `invalid_signature` / `project_not_allowed` / `org_mismatch`;
`400` for `schema_invalid` / `timestamp_skew`. D-4 POSTs against the **pinned**
`1.3-draft` contract (D-0018).

## Resolved design forks (this plan ratifies these)

1. **Delivery trigger → a ledger-relay / drain worker.** A **separate relay** reads
   iplan-runner's durable append-only ledger, projects each ledger event to the Iplanic
   `execution-event` shape (`to_execution_events`), signs it (`iplanic_signing.sign`), and
   `POST`s it — advancing a **durable cursor**. This is decoupled from the run loop,
   **resumable** (the cursor survives executor restart), and **survives Iplanic
   downtime** (retry with backoff; the cursor only advances on success). It is symmetric
   with D-3's outbox-consumer worker. The inline-emit alternative (POST at append) was
   rejected: it couples execution progress to Iplanic availability and risks event loss.
2. **Integration-test target → an in-process fake Iplanic server.** The gated,
   integration-only suite POSTs against a **small in-process HTTP server** that mimics the
   `/v1/events` contract (202 + the reject envelope/status codes), so the suite is
   hermetic, Docker-free, and carries **no sibling-repo dependency** — mirroring PLAN-008's
   "opt-in, keyed, not in CI" pattern. Drift risk (the fake diverging from real Iplanic)
   is mitigated by deriving the fake's responses from the **documented reject codes** + the
   already-vendored, version-pinned **`framework/remote/iplanic-vectors/`** corpus.

## Design content to specify (the deliverable — descriptions, not code)

1. **The ledger-relay / drain worker.** Reads the durable ledger in append order;
   per event: project (`to_execution_events`) → sign (`iplanic_signing.sign`) → `POST
   /v1/events` **verbatim** → on `202`, advance the **durable cursor**. The POST body is
   the projected event **as-is, including the placeholder `received_at` (= `occurred_at`)**:
   `received_at` is schema-**required** and validated **before** the precedence, so omitting
   it is a `400 schema_invalid`; Iplanic overwrites it post-acceptance and it is **excluded
   from the signature** (so the placeholder is safe). **At-least-once** (the cursor advances
   only after a `202`; a crash between POST and cursor-write re-POSTs, which Iplanic
   **dedups by `idempotency_key`**).

   **Stable `idempotency_key` (load-bearing for dedup).** That dedup only works if the
   `idempotency_key` is a **deterministic function of the ledger event's stable identity**.
   It currently is **not**: `_build_event` derives `event_id = ids("EV")` and
   `idempotency_key = f"{run_id}:{event_id}"` from a **positional** `IdSource` ordinal
   counter (`"EV1","EV2",…`, fresh per projection pass) — so a non-byte-identical
   re-projection (different cursor offset, a grown ledger, skip-set interactions) yields
   **different** keys for the *same* logical event, defeating dedup. D-4 therefore
   **requires** anchoring the `idempotency_key`/`event_id` to the **D-0008 hash-chain
   identity** (the ledger event's `sequence` / `event_hash`, `ledger/store.py`
   `compute_event_hash`), making re-POST idempotent regardless of re-projection. This is a
   **value-derivation** change to the emit projection in D-4b (the wire **field** is
   unchanged — not a contract/shape change).

   **Per-engine** (D-0011 strict isolation): each engine (`hermes`/`claude`) ships its own
   relay + client (no shared code); the contract + vectors in `framework/remote/` are the
   shared **data**. The two relays are **not** differential-tested (live transport is out of
   cross-engine parity, PLAN-008 / D-0013); each engine's own integration suite holds its
   relay.
2. **The transport-client interface** — mirrors PLAN-008's per-engine live-executor client
   (`ApiExecutor`/`HostRuntimeExecutor`): a configured endpoint, a bearer-token provider,
   bounded retry/backoff, and a single `deliver(event) -> Outcome`. Described as an
   interface, not code.
3. **Auth/token seam.** The caller attaches a **bearer token** (D-0015 agent-first
   identity / Iplanic D-0017 JWT). D-4 specifies an **injected token-provider seam** (a
   static token in tests; real OIDC/JWKS acquisition deferred, like Iplanic's `CallerAuth`
   fake). On `401 unauthenticated` the provider is asked to refresh once, then escalate.
4. **Reject-code → outcome map** (the response-handling core):
   - `202` (accept **or** idempotent replay) → **success**; advance cursor.
   - `timestamp_skew` → the reject envelope carries **no sub-cause** (Iplanic collapses
     both bounds into one `reason="timestamp_skew"`, `detail` just echoes it), so the relay
     **cannot** read future-skew vs stale from the response. The relay therefore
     **classifies locally** — a *heuristic*, since the bounds are Iplanic-side config
     (documented defaults `FUTURE_SKEW = 300s` / `MAX_AGE = 86400s`): an event whose
     `occurred_at` is far past `MAX_AGE` is treated **terminal → dead-letter** (it can
     never be accepted); otherwise **retry-with-cap** (covers transient future-skew and
     borderline cases), then dead-letter on cap. The design states this is a local
     heuristic, not a server-driven split.
   - `invalid_signature` / `schema_invalid` → **terminal, escalate + halt**: these mean a
     signing/projection bug and must never happen given the frozen conformance — a loud
     failure, not a silent drop.
   - `unregistered_executor` / `executor_not_active` / `project_not_allowed` /
     `org_mismatch` → **terminal, escalate** (admin/registration/scope — outside the
     executor's control); **dead-letter** so one event does not block the queue. Note:
     because Iplanic's caller↔`executor_id` binding is **deferred** (D-2 auth is an on/off
     gate), an executor-identity mismatch surfaces **here** (403), **not** as `401` — so
     "401 = creds" but these 403s = identity/registration.
   - `unauthenticated` (401) → token invalid/missing only → refresh token once → else
     terminal/escalate (creds).
   - transport faults (network, timeout, `5xx`) → **retryable** with bounded backoff.
5. **Cursor + dead-letter.** The relay holds a **durable cursor** over the ledger. To
   avoid **head-of-line blocking**, a **terminal** reject moves that event to a
   **dead-letter / escalation** sink (recorded, surfaced) and the cursor advances past it;
   only **retryable** outcomes hold the cursor. **The dead-letter sink carries the same
   durability obligation as the cursor**, and the cursor advances past a terminal reject
   **only after** the dead-letter write is **durably committed** (write-ordering) —
   otherwise advancing the (forward-only) cursor past an un-acceptable event is silent
   loss, the exact failure fork 1 exists to prevent. This keeps a single un-acceptable
   event from stalling all delivery without dropping it.
6. **Config seam** — endpoint URL, token provider, retry/backoff bounds, batch size,
   dead-letter sink — injected (mirroring PLAN-008 config/secrets and Iplanic's D-2 port
   injection); no live credentials or endpoint baked in.
7. **Integration-test strategy** — the in-process fake Iplanic server (fork 2): what it
   asserts (a `202` advances the cursor + is idempotent on redelivery; each reject class
   maps to the right outcome incl. the skew future-vs-stale split; terminal rejects
   dead-letter without stalling; auth-refresh-once), the opt-in marker, and the
   fake-vs-real drift mitigation via the pinned vectors.
8. **ADR — propose D-0020** recording the D-4 architecture (the two forks + the
   outcome map + the dead-letter cursor model) for ratification.

## Out of scope (explicitly — design stage)

- **Any source code, the HTTP client, the relay/worker, the fake server, or tests** — the
  build is the **D-4b** plan, authored after this design is approved.
- Re-doing the event projection / signing (frozen by D-0016 + the conformance suite).
- The **real OIDC/JWKS** token acquisition (seam only, deferred like Iplanic's auth).
- Any change to the Iplanic service, its endpoint, or the vendored contract/vectors.
- iplan-runner's standalone run loop, ledger, gate, or monitoring (D-4 only *reads* the
  ledger to relay).

## Tasks (documentation only)

1. **Write the D-4 transport design** (this plan's body + a companion `framework/remote/`
   or `docs/` design note as needed) covering items 1–7: the relay/cursor model, the
   per-engine client interface, the auth/token seam, the retry/at-least-once policy, the
   reject→outcome map, and the fake-server integration strategy.
2. **Specify the interfaces** (transport client, token provider, dead-letter sink) as
   descriptions, not code; note they are **per-engine** (D-0011).
3. **Propose D-0020** (the D-4 architecture decision) for ratification; tick the
   Phase D / D-4 row in the iplanic FOLLOWUP-PROGRAM as "design ready" (cross-repo note).
4. **Hand off to D-4b** — enumerate the build-stage deliverables (the HTTP client, the
   relay worker, the cursor/dead-letter store, the fake-server integration suite, the
   real token provider) the design unblocks.

## Verification (design-stage)

- The design covers both resolved forks + the full reject-code → outcome map (incl. the
  `timestamp_skew` future-vs-stale split and the dead-letter cursor), and is **consistent
  with** the frozen emit contract (`REMOTE_EXECUTOR_CONTRACT.md` / `to_execution_events` /
  `iplanic_signing`), the pinned Iplanic `1.3-draft` endpoint contract (D-0018), and the
  decisions D-0011/D-0015/D-0016 (no contradiction).
- **No `platforms/**` code, no `framework/` contract change, no migration, no tests** are
  added by this plan (only docs/plan).
- D-0020 is **ratified in this PR** (added to `DECISIONS.md`, newest-first), on approval/merge; the gate passes.

## Claim ledger

> Every load-bearing claim cites the `file:line` actually read. All in-repo (iplan-runner);
> the Iplanic endpoint contract (202 / reject codes) is cross-repo and described narratively.

| #   | Claim | Symbol | Citation |
| --- | ----- | ------ | -------- |
| 1   | iplan-runner already emits signed `execution-event`s **by projecting its own ledger** (the source D-4 relays) | `projecting its own signed ledger` | framework/remote/REMOTE_EXECUTOR_CONTRACT.md:6 |
| 2   | the contract defines the **Ledger → `execution-event` projection** (per ledger event) | `Ledger → ` | framework/remote/REMOTE_EXECUTOR_CONTRACT.md:47 |
| 3   | `to_execution_events` is the projection function the relay consumes (ledger → Iplanic events) | `def to_execution_events` | platforms/hermes/src/iplan_hermes/ledger/events.py:84 |
| 4   | `iplanic_signing.sign` is the conformance-proven Iplanic-shape signer (no re-derivation in D-4) | `def sign` | platforms/hermes/src/iplan_hermes/security/iplan_canonical/signing.py:37 |
| 5   | D-0016 made the remote-executor contract **transport-agnostic** — D-4 fills the transport gap | `transport-agnostic` | plans/DECISIONS.md:273 |
| 6   | PLAN-008 established the **per-engine live-executor client** pattern D-4's transport mirrors | `ApiExecutor` | plans/PLAN-008_config-live-executors.md:9 |
| 7   | PLAN-008's live clients are **opt-in, keyed, not in CI** — the integration-gating pattern D-4's suite mirrors | `not in CI` | plans/PLAN-008_config-live-executors.md:21 |
| 8   | D-0011 strict engine isolation → the transport is **per-engine** (no shared code) | `Strict engine isolation` | plans/DECISIONS.md:100 |
| 9   | D-0015 (agent-first identity) is the bearer-token / auth basis for the transport | `agent-first` | plans/DECISIONS.md:292 |
| 10  | D-0018 pins the Iplanic `1.3-draft` contract the transport POSTs against | `Re-pin Iplanic mirrors to` | plans/DECISIONS.md:233 |
| 11  | the highest existing decision is D-0019 (so the proposed ADR is D-0020) | `D-0019` | plans/DECISIONS.md:217 |
| 12  | the projection derives `idempotency_key` from a per-call `event_id` (the dedup key the relay depends on) | `idempotency_key` | platforms/hermes/src/iplan_hermes/ledger/events.py:71 |
| 13  | `event_id` comes from a **positional** ordinal `IdSource` (`EV1`,`EV2`,…) — fresh per pass, **not** content-stable | `def __call__` | platforms/hermes/src/iplan_hermes/executor/base.py:39 |
| 14  | the ledger already has a **stable identity** (`compute_event_hash(sequence, previous_event_hash, …)`) the relay must anchor the key on | `def compute_event_hash` | platforms/hermes/src/iplan_hermes/ledger/store.py:12 |
| 15  | D-0008 is the append-only **hash-chained** ledger (the stable identity source) | `hash-chained` | plans/DECISIONS.md:68 |
| 16  | the projection sets `received_at = occurred_at` as the placeholder (Iplanic overwrites at ingest) — the relay must POST it | `received_at` | platforms/hermes/src/iplan_hermes/ledger/events.py:75 |

## Review log

> ≥2 passes before ready. ≥1 independent fresh-context (`Agent`). Final pass states
> zero findings.

### Pass 1 - 2026-06-14 - author

- Verified all 11 ledger citations by opening each file at the cited line.
- Confirmed the **design-stage** scope: this plan produces design/spec/ADR only — no
  `platforms/**` code, no `framework/` contract change, no tests (the build is D-4b). The
  two forks are ratified per the user's decisions (ledger-relay/drain worker; in-process
  fake Iplanic server).
- Confirmed D-4 is **only transport**: the event projection (`to_execution_events`) and
  the signer (`iplanic_signing.sign`) already exist and are conformance-proven (D-0016 was
  transport-agnostic), so the design adds delivery — not event shape or signing.
- Open questions for the independent pass: (a) is `timestamp_skew` actually splittable
  into future-skew (retryable) vs stale/MAX_AGE (terminal) from the executor side, or does
  the reject envelope not carry enough to distinguish them (forcing a single
  classification)? (b) does the **per-engine** relay (D-0011) duplicate non-trivial
  transport logic the design should acknowledge, or is a shared *contract* (data) enough?
  (c) does advancing the cursor past a **dead-lettered** terminal reject risk silently
  dropping events the operator must act on — is the escalation sink's durability part of
  the design? (d) does the at-least-once cursor + `idempotency_key` dedup actually hold if
  the ledger can be **re-projected** to a *different* `event_id` for the same logical event
  (would break Iplanic's `idempotency_key`-based replay)?

### Pass 2 - 2026-06-14 - independent

Fresh-context reviewer re-verified the ledger (11/11 original rows accurate) and read both
sides — the iplan-runner emit surface and the **iplanic** endpoint/precedence. Design-stage
purity confirmed (only the plan changes; the projection + signer are untouched). It found
**4 load-bearing gaps** — all folded in (ledger rows 12-16 added):

- **(a) `timestamp_skew` is not server-distinguishable.** iplanic collapses both skew
  bounds into one `reason="timestamp_skew"` with a `detail` that just echoes the reason
  (`iplanic_service/precedence.py` `_within_skew`; `app.py` reject), so the relay can't read
  future-skew vs stale from the response. → Item 4 rewritten: the relay classifies
  **locally** (an explicit heuristic against the documented default bounds), not by a
  server-driven split.
- **(b) `idempotency_key` is positional, not content-stable** (the most serious).
  `_build_event` derives `event_id` from a fresh `IdSource` ordinal counter
  (`events.py:54`, `executor/base.py:39`), so a non-byte-identical re-projection produces
  different keys for the same logical event and defeats iplanic's `idempotency_key` dedup.
  → Item 1 now **requires** anchoring the key on the **D-0008 hash-chain identity**
  (`compute_event_hash` `sequence`/`event_hash`) — a value-derivation change in D-4b, not a
  wire-shape change (rows 12-15).
- **(d) Dead-letter durability was unstated.** Advancing the forward-only cursor past a
  dead-lettered terminal reject is silent loss unless the sink is durable. → Item 5 now
  requires the dead-letter sink carry the **same durability** as the cursor, with the cursor
  advancing only after a durable dead-letter commit (write-ordering).
- **(e) `received_at` is schema-`required` and validated before precedence**, so the relay
  must POST a placeholder or get `400 schema_invalid`. → Item 1 now states the relay POSTs
  the event **verbatim** including `received_at = occurred_at` (overwritten post-acceptance,
  excluded from the signature) (row 16).

Minor, folded in: the auth `401` covers token validity only — an executor-identity mismatch
surfaces as `403` (binding deferred, D-2 on/off gate), not `401`; and the two per-engine
relays are not differential-tested (live transport is out of cross-engine parity,
PLAN-008/D-0013) — each engine's own integration suite holds it.

**No remaining load-bearing findings.**

**Result:** ready — no further findings.
