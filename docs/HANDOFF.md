# iplan-runner — Session Handoff

> Durable resume doc. Updated **2026-06-14**. iplan-runner is the **OSS IPLAN executor**
> (the former engineering codename was dropped; see D-0019). All Phase-D
> design is done + ratified; the next work here is the **D-4b BUILD** — when you move past
> the design stage.

## Repo state

- **`main`, clean.** Remote `https://github.com/vladm3105/iplan-runner`.
- Python packages are **`iplan_hermes` / `iplan_claude`** (renamed from `iops_*`).
- Already a **conformant Iplanic remote executor** (D-0016, transport-agnostic): it emits
  signed `execution-event`s in Iplanic's shape by projecting its own ledger
  (`platforms/<engine>/src/iplan_<engine>/ledger/events.py:to_execution_events`), signed by
  `security/iplanic_signing.py`. Conformance-proven (PLAN-013/014/015).
- Dual-engine **strict isolation** (D-0011): `hermes` + `claude` share no code, only
  `framework/` data; behavioral parity via golden vectors.

## What's pending here: D-4b (the BUILD of the D-4 transport)

The **design is merged**: `plans/PLAN-017_d4-iplanic-transport-design.md` + decision
**D-0020** (`plans/DECISIONS.md`). D-4b implements it. Author a verified-planning
**PLAN-018** (D-4b) first, then build. The design already resolved the hard parts:

- **Ledger-relay / drain worker** (per-engine, no shared code): reads the durable ledger in
  append order → project (`to_execution_events`) → sign (`iplanic_signing.sign`) → `POST`
  to iplanic `/v1/events` **verbatim** (incl. placeholder `received_at = occurred_at`) →
  on `202`, advance a **durable cursor**.
- **⚠ The load-bearing implementation note:** the `idempotency_key`/`event_id` MUST anchor
  on the **D-0008 hash-chain identity** (`ledger/store.py:compute_event_hash` → `sequence`/
  `event_hash`), **NOT** the current positional `IdSource` counter
  (`ledger/events.py:_build_event`, `event_id = ids("EV")`). The positional derivation makes
  re-projection produce different keys for the same event → defeats iplanic's
  `idempotency_key` dedup. This is a value-derivation change to the emit projection (the
  wire field is unchanged).
- **Reject → outcome map:** `202` → success/advance; `timestamp_skew` → classify **locally**
  (heuristic — iplanic gives no sub-cause): far-stale → dead-letter, else retry-with-cap;
  `invalid_signature`/`schema_invalid` → terminal+halt (a bug); registration/scope (403) →
  terminal+escalate → **dead-letter**; `401` → refresh token once → escalate; transport
  faults/5xx → retry-with-backoff.
- **Cursor + dead-letter must both be durable**; the cursor advances past a terminal reject
  **only after** a durable dead-letter commit (no silent loss).
- **Auth:** injected bearer-token provider seam (real OIDC deferred; static token in tests).
- **Integration suite:** an **in-process fake iplanic server** (mimics `/v1/events`: 202 +
  reject envelope/status), gated/opt-in (PLAN-008 "not in CI" pattern); drift mitigated by
  the pinned `framework/remote/iplanic-vectors/`.
- The endpoint contract: iplanic `POST /v1/events` → `202 {event_id}` (also idempotent
  replay) or `{reason, detail}` at 401/403/400; pinned `1.3-draft` (D-0018).

## Working protocol (this repo's specifics)

- **Verified-planning** is mandatory: cited Claim ledger + ≥2 passes incl. ≥1 independent
  fresh-context `Agent` review (often a 2nd from-scratch pass — they keep catching real
  load-bearing bugs), then `python .claude/skills/verified-planning/check_plan.py <plan>`.
- **Never merge** without the user's command. Branch + PR; the user merges and replies
  "merged and remote deleted" → then sync + prune.
- **Branch protection:** PRs need **1 approval** to merge.
- `git push` works over SSH (no token tricks); **`gh` needs `env -u GH_TOKEN -u GITHUB_TOKEN`**.
- **CI gotchas:** (1) the **`pre-commit --all-files`** job ("Lint / format / security hooks")
  gates **every** plan — inserting a `DECISIONS.md` entry shifts line numbers and breaks
  **other** gated plans' citations (refresh them all). (2) **PLAN-001..012 are
  grandfathered** out of the gate in pre-commit but **NOT** in CI `plan-gate.yml` — editing a
  001..012 plan fails CI (no Claim ledger); leave them. (3) mypy passes in CI's fresh `[dev]`
  env; local `types-PyYAML` makes harmless `unused-ignore` noise — don't "fix" the
  `# type: ignore[import-untyped]` lines. (4) CodeQL ("Analyze Python") is slow (~3 min) —
  not a failure.
- Next **decision** = **D-0021**; next **plan** = **PLAN-018**. `plans/DECISIONS.md` is
  `### D-00NN` prose (mixed order; D-0001..D-0013 ascending, then a newest-first block —
  insert new decisions at the **top of the newest block**, before D-0019).

## TODO

- [ ] **(when moving past design) Author PLAN-018 = D-4b** (verified-planning) and build the
      transport per PLAN-017 / D-0020 — relay+cursor, transport client, auth seam, reject map,
      durable dead-letter, fake-server integration suite.
- [ ] Within D-4b: change the emit projection's id derivation to anchor `idempotency_key` on
      the hash-chain `sequence`/`event_hash` (the ⚠ note above).

## Sibling: iplanic (the standard + ingestion service)

The `aidoc-flow-iplanic` repo (private — planned public) — D-1/D-2 **built**;
D-3 design (PLAN-015, D-0034) merged; **D-3b** (the PostgreSQL build) is its
pending counterpart.
