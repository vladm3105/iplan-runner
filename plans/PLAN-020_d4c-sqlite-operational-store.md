# D-4c — SQLite Operational Store (sync-friendly)

> Development plans follow the SDD workflow inherited from
> `aidoc-flow-framework`: **plan → review (≥2 passes) → implement → verify →
> land**. ≥2 review passes recorded in `## Review log`, ≥1 independent
> fresh-context, before implementation; harden until a pass finds nothing.
>
> **Size to the problem.** This moves the relay's *operational* state to SQLite
> per D-0021 — it does not touch the signed ledger or add a design surface.

**Goal:** Re-home the executor's **operational** relay state (settled-cursor,
dead-letter, persisted iplanic identity) from JSON sidecars to a single per-store
**SQLite** database (stdlib `sqlite3`, **no new dependency**), shaped as an
**outbox keyed on the stable `idempotency_key`** so on-demand iplanic sync is a
clean, transactional drain. The signed hash-chained **ledger stays a portable
file** (unchanged). Per-engine (`hermes` + `claude`), parity proven by the
existing gated suite. Implements **D-0021**.

**Architecture:** `relay/store.py` is re-implemented over `sqlite3` **behind its
current public interface**, so `relay/worker.py` and the CLI `sync` are unchanged
and the D-4b gated suite regresses it. One `relay.db` per store directory
(`<store>/relay.db`), keyed by `ledger_id`. The D-4b two-write invariant
(dead-letter commit *then* cursor advance) collapses into **one atomic
transaction** (the dead-letter row *is* the cursor mark). No `framework/` change.

**Tech Stack:** Python ≥3.11 stdlib `sqlite3` (WAL), `unittest`/`pytest`. No deps.

---

| Field      | Value |
|------------|-------|
| Task       | D-4c (operational-store hardening of the D-4b transport) |
| Depends on | **D-0021**; D-4b (PLAN-019, the relay it backs); D-0008 (hash-chain identity); D-0011 (isolation) |
| Status     | PLANNED - 2026-06-15 |
| Feeds      | The "online (with iplanic)" + on-demand-sync operating modes (durability + sync-friendliness) |

## Objective

D-4b delivered the relay over JSON sidecar files. Its at-least-once invariant —
dead-letter commit **before** the cursor advances — is currently **two separate
atomic writes** (`relay/store.py:dead_letter` then `mark_settled`), so a crash
between them re-POSTs the event (iplanic dedups it) and double-writes a dead-letter
entry. D-4c makes the operational state a transactional, indexed SQLite **outbox**
so dead-letter + settle is one atomic row, queries are indexed, and concurrent
syncs are safe — while keeping the signed ledger a portable file and adding no
dependency.

## Scope

**In:**

1. **SQLite operational store** (`relay/store.py`, both engines, same public
   interface). One `relay.db` per store dir; `PRAGMA journal_mode=WAL` +
   `busy_timeout`. Two tables:
   - `delivery(ledger_id, idempotency_key, status, reason, event_json, updated_at)`,
     PK `(ledger_id, idempotency_key)`; `status ∈ {delivered, dead_lettered}`.
   - `identity(ledger_id, identity_json)`, PK `ledger_id`.
2. **Outbox semantics keyed on `idempotency_key`** (the key iplanic dedups on):
   `load_settled` = the set of keys with a row; `mark_settled` = insert a
   `delivered` row; `dead_letter` = insert a `dead_lettered` row **in one
   statement** (so it *is* the cursor mark — the D-4b two-write window is gone);
   `load_dead_letter` = rows where `status='dead_lettered'`. Identity via the
   `identity` table.
   **Interface preserved byte-for-byte** (so `worker.py`/CLI/the gated suite are
   the regression oracle):
   - `dead_letter` keeps its current signature `(store_dir, ledger_id, entry)` and
     **unpacks the `entry` dict internally** (`entry["event"]→event_json`,
     `entry["reason"]→reason`) — `worker.py:63`'s call is unchanged (F1).
   - `load_dead_letter` returns the **same shape** as today —
     `list[{"event": <parsed event_json>, "reason": <reason>}]` — so the gated
     suite's `dl[0]["reason"]` assertion (`test_iplanic_transport.py:103`) holds (F2).
   - `save_identity` still **returns** the persisted identity dict — the CLI
     `_sync` binds it (`cli/commands.py:135`) (F7).
3. **Worker simplification** (`relay/worker.py`): the dead-letter branch calls the
   single atomic `dead_letter` (drops the now-redundant follow-up `mark_settled`).
   Delivered/retry/halt behavior unchanged.
4. **Tests:** unit tests for the SQLite store (atomic dead-letter=settle, WAL
   re-open persistence, concurrent-writer `busy_timeout`, idempotent re-insert) +
   the D-4b gated suite re-run green against the SQLite backend (regression).
5. Both engines, no shared code; parity via the suite (D-0011/D-0012).

**Out:**

1. **The signed ledger** (`ledger/persistence.py`, YAML) — stays a portable,
   independently verifiable file (D-0021 role 1). Not moved.
2. **The run index/status** (`ledger/index.py`, which globs the ledger files) —
   reads the file ledgers, which stay; SQLite-backed status is a later item.
3. **Back-compat migration** of existing JSON sidecars — pre-1.0, none.
4. Any wire-shape / `framework/` change, or iplanic-side change.
5. A long-running daemon / auto-sync (still on-demand, per D-4b Out).

## Approach

`relay/store.py` keeps every current function signature (`load_settled`,
`mark_settled`, `dead_letter`, `load_dead_letter`, `save_identity`,
`load_identity`) so its consumers — `relay/worker.py` and the CLI `sync` — do not
change. The bodies switch from `_atomic_write_json` over dot-files to `sqlite3`
statements against `<store>/relay.db`, opened per call (short-lived connection,
WAL + `busy_timeout` for concurrent syncs), schema created idempotently with
`CREATE TABLE IF NOT EXISTS`.

The **outbox keyed on `idempotency_key`** is what makes sync clean and iplanic-
symmetric: a projected event is "settled" iff a `delivery` row exists for its key,
exactly the key iplanic dedups on (D-4b anchored it on the D-0008 `event_hash`).
The drain stays "events whose key has no row → POST → write row," but the
dead-letter path is now a **single `INSERT`** that records the reason/event **and**
marks the cursor in one transaction — eliminating the D-4b crash-window
(`relay/worker.py:63-64`). This mirrors iplanic's own transactional-outbox
ingestion (its D-3b), so at-least-once is reasoned about identically end-to-end.

Per D-0011, implemented twice (hermes + claude, byte-parallel); the gated
integration suite runs against both and is the parity proof.

## File Structure

| Path | Responsibility |
|------|----------------|
| `platforms/<engine>/src/iplan_<engine>/relay/store.py` | Re-implement over `sqlite3` behind the current interface; add the schema + WAL |
| `platforms/<engine>/src/iplan_<engine>/relay/worker.py` | Dead-letter branch uses the single atomic `dead_letter` (drop the trailing `mark_settled`) |
| `platforms/<engine>/tests/test_relay_store.py` | New unit tests for the SQLite store (atomicity, WAL, concurrency, persistence) |

## Step Sequence

### Task 1: SQLite operational store (both engines)

- [ ] **Step 1:** Re-implement `relay/store.py` over `sqlite3`: `_connect(store_dir)`
  opens `<store>/relay.db` with `journal_mode=WAL` + `busy_timeout=5000`, runs
  `CREATE TABLE IF NOT EXISTS` for `delivery` + `identity`. Re-implement the six
  public functions **against the unchanged signatures**: `dead_letter` keeps
  `(store_dir, ledger_id, entry)` and is a single `INSERT OR REPLACE` writing
  `status='dead_lettered'`, `reason=entry["reason"]`, `event_json=json(entry["event"])`
  (so the row is both the dead-letter record and the cursor mark); `load_dead_letter`
  rebuilds `{"event": json.loads(event_json), "reason": reason}` rows; `mark_settled`
  inserts a `delivered` row; `save_identity` returns the persisted dict. The WAL
  sidecars (`relay.db-wal`/`-shm`) sit in `<store>/` and do not affect
  `ledger/index.py:35`'s `*.yaml` glob.
- [ ] **Step 2: Commit** (per engine) `refactor(relay): SQLite operational store (cursor/dead-letter/identity), outbox-shaped (D-4c)`

### Task 2: Worker uses the atomic dead-letter

- [ ] **Step 1:** In `relay/worker.py`, the **sole change** is deleting the
  now-redundant trailing `store.mark_settled(store_dir, ledger_id, idem)`
  (`worker.py:64`) — the atomic `store.dead_letter(...)` on `worker.py:63` now
  settles the key by itself. The `dead_letter` **call shape is unchanged** (still
  `{"event": event, "reason": outcome.reason}`). Delivered/retry/halt branches
  untouched. (A `dead_lettered` key is already skipped on the next sync via the
  `idem in settled` guard at `worker.py:56`, so no `INSERT OR REPLACE` status flip.)
- [ ] **Step 2: Commit** `fix(relay): atomic dead-letter+settle via the SQLite outbox (D-4c)`

### Task 3: Tests (SQLite store unit + gated regression)

- [ ] **Step 1:** `tests/test_relay_store.py` (per engine): atomic dead-letter==settle
  (one row, appears in both `load_settled` and `load_dead_letter` with the
  `{"event":…, "reason":…}` shape); a `dead_lettered` key reads back as settled and
  is **not** flipped to `delivered` (F4); WAL re-open persistence; concurrent-writer
  does not error under `busy_timeout`; idempotent re-insert; `save_identity`
  round-trips and returns the dict. Re-run the D-4b gated suite
  (`IPLAN_FAKE_IPLANIC=1`) green against the SQLite backend.
- [ ] **Step 2: Commit** `test(relay): SQLite operational-store unit tests + gated regression (D-4c)`

### Task 4: Docs

- [ ] **Step 1:** `CHANGELOG.md` `[Unreleased]`; refresh `plans/HANDOFF.md`,
  `TODO.md`, `ROADMAP.md`; mark this plan `Status: DONE`.

## Verification

> Nothing is "done" until these pass.

```bash
python -m unittest discover -s tests/conformance        # unchanged — ledger/wire untouched
pytest platforms/hermes platforms/claude -q              # incl. the new SQLite store unit tests
ruff check platforms && mypy --strict platforms/hermes/src platforms/claude/src
IPLAN_FAKE_IPLANIC=1 pytest platforms/hermes/tests/test_iplanic_transport.py \
  platforms/claude/tests/test_iplanic_transport.py -q    # the D-4b suite, now on SQLite
# a crash between dead-letter and the (gone) second write can no longer double-write:
#   the dead-letter unit test asserts one row settles + records in a single transaction
```

Expected: conformance unchanged (ledger + wire untouched); the gated suite passes
against the SQLite backend; the new unit tests prove the atomic dead-letter=settle,
WAL persistence, and concurrency safety; no new dependency in `pyproject.toml`.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | SQLite swap changes relay behavior | Same public interface; the D-4b gated suite re-runs green as the regression oracle (R-table mirrors PLAN-019) |
| R2 | Engine drift (hermes vs claude store diverge) | Per-engine but byte-parallel; the same suite runs against both (D-0011/D-0012) |
| R3 | Concurrent syncs corrupt the cursor | WAL + `busy_timeout`; a concurrent-writer unit test; single-statement settles are atomic |
| R4 | Lost evidence portability | Out of scope by design — the signed ledger stays a YAML file (D-0021); only operational state is in SQLite |
| R5 | A hidden new dependency | `sqlite3` is stdlib; a test/assert that `pyproject.toml` deps are unchanged |

## Claim ledger

> Every load-bearing claim cites the `file:line` actually read.

| # | Claim | Symbol | Citation |
|---|-------|--------|----------|
| 1 | The relay store is JSON-sidecar-file-based today (the thing being replaced) | `tmp.write_text` | platforms/hermes/src/iplan_hermes/relay/store.py:28 |
| 2 | The store's public read surface the worker/CLI depend on | `def load_settled` | platforms/hermes/src/iplan_hermes/relay/store.py:35 |
| 3 | `dead_letter` is a separate write today (collapses into the atomic settle) | `def dead_letter` | platforms/hermes/src/iplan_hermes/relay/store.py:60 |
| 4 | The two-write invariant: dead-letter **then** cursor advance | `store.mark_settled` | platforms/hermes/src/iplan_hermes/relay/worker.py:64 |
| 5 | The cursor read the drain filters on | `store.load_settled` | platforms/hermes/src/iplan_hermes/relay/worker.py:52 |
| 6 | Identity persists the 8 fields (moves to the `identity` table) | `payload.get` | platforms/hermes/src/iplan_hermes/relay/store.py:71 |
| 7 | No new dependency — deps are pyyaml/rfc8785/cryptography (sqlite3 is stdlib) | `dependencies` | platforms/hermes/pyproject.toml:10 |
| 8 | iplanic dedups on `idempotency_key` — so it is the outbox key (the contract prose at :52 still shows the pre-D-4b `{run_id}:{event_id}` formula; the code of record is row 9) | `idempotency_key` | framework/remote/REMOTE_EXECUTOR_CONTRACT.md:52 |
| 9 | `idempotency_key` is anchored on the D-0008 `event_hash` (stable outbox key) | `idem = f"{run_id}` | platforms/hermes/src/iplan_hermes/ledger/events.py:27 |
| 10 | The signed ledger stays a portable YAML file (evidence role, not moved) | `yaml.safe_dump` | platforms/hermes/src/iplan_hermes/ledger/persistence.py:31 |
| 11 | The run index globs the ledger files (out of scope; files stay) | `glob` | platforms/hermes/src/iplan_hermes/ledger/index.py:35 |
| 12 | D-0011 strict engine isolation (implement per-engine, no shared code) | `### D-0011` | plans/DECISIONS.md:100 |
| 13 | The decision this builds | `### D-0021` | plans/DECISIONS.md:155 |
| 14 | The D-4b gated suite exercises the store (the regression oracle) | `relay_store.load_dead_letter` | platforms/hermes/tests/test_iplanic_transport.py:102 |
| 15 | The `claude` engine has the byte-parallel store interface (parity scope) | `def dead_letter` | platforms/claude/src/iplan_claude/relay/store.py:60 |

## Review log

> ≥2 passes before implementation; ≥1 independent fresh-context review.

### Pass 1 - 2026-06-15 - author self-review

- Drafted from D-0021. Confirmed every citation by grep against the post-D-4b tree
  (store.py 28/35/60/71, worker.py 52/64, events.py 27, persistence.py 31,
  index.py 35, pyproject 10, contract 52, DECISIONS 100/155, the gated test 102).
- Sized to D-0021: operational state only; the ledger and the run index are
  explicitly out. The interface-preserving swap keeps `worker.py`/CLI/the gated
  suite as the regression oracle — no new design surface.
- Key load-bearing point recorded: the single-`INSERT` dead-letter *is* the cursor
  mark, which is what removes the D-4b two-write crash-window and keys the outbox on
  `idempotency_key` for iplanic-symmetric sync.

### Pass 2 - 2026-06-15 - independent (general-purpose Agent, fresh context)

All 14 original citations verified accurate. The core claim — one `INSERT OR REPLACE`
makes the dead-letter row *be* the cursor mark — confirmed sound (the only two settle
sites are `worker.py:60` ADVANCE and `worker.py:62-64` DEAD_LETTER; the CLI `_sync`
only reads). Two **[BLOCKING]** internal inconsistencies + four [SHOULD]/[NIT] found
and folded:

- **[BLOCKING] F1 — `dead_letter` signature vs "worker unchanged".** The worker passes
  an `entry` dict (`worker.py:63`); the plan implied separate `(reason, event_json)`
  args. **Fixed:** `dead_letter` keeps `(store_dir, ledger_id, entry)` and unpacks
  internally; Task 2's sole worker change is deleting the trailing `mark_settled`
  (`worker.py:64`). (Scope 2; Task 1/2.)
- **[BLOCKING] F2 — `load_dead_letter` return shape.** The gated suite asserts
  `dl[0]["reason"]` (`test_iplanic_transport.py:103`). **Fixed:** the plan now requires
  `load_dead_letter` to rebuild the byte-identical `[{"event":…, "reason":…}]` shape;
  a unit test asserts it. (Scope 2; Task 1/3.)
- **[SHOULD] F3 — claim 8's cited contract line is stale** (`{run_id}:{event_id}` vs the
  code's `event_hash` anchor). **Fixed:** claim 8 reworded to note the staleness and
  defer to row 9 (`events.py:27`) as the code of record; the contract is `framework/`,
  so a doc-fix stays out of scope (GATE-SPEC).
- **[SHOULD] F4 — no status flip.** A re-projected `dead_lettered` key must not flip to
  `delivered`. **Confirmed safe** by the `idem in settled` skip (`worker.py:56`); added
  a unit test asserting it. (Task 3.)
- **[SHOULD] F5 — concurrency specifics.** **Fixed:** `busy_timeout=5000`; noted the WAL
  `-wal`/`-shm` sidecars don't affect `index.py:35`'s `*.yaml` glob. (Task 1.)
- **[SHOULD] F6 — claude parity unverified.** **Fixed:** added claim 15 citing
  `platforms/claude/.../relay/store.py:60` (identical interface).
- **[NIT] F7 — `save_identity` must return the dict** (CLI binds it). **Fixed:** stated
  in Scope 2 + Task 1.

### Pass 3 - 2026-06-15 - author confirmation

Re-verified against source: `worker.py:63` passes `{"event":…, "reason":…}` (F1 fix is
call-compatible); `test_iplanic_transport.py:103` asserts `dl[0]["reason"]` (F2 shape
requirement exact); `cli/commands.py:135` binds `save_identity`'s return (F7);
`claude/.../relay/store.py:60` `def dead_letter(..., entry)` matches hermes (F6 parity).
All 15 citations resolve. No new load-bearing findings.

**Result: ready** — buildable; the interface-preserving swap keeps `worker.py`/CLI/the
gated suite as the regression oracle.
