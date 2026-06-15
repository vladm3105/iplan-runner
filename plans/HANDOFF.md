# iplan-runner — Session Handoff

> Durable resume doc — the **canonical** handoff for this repo (per `CLAUDE.md`).
> Sessions run in ephemeral containers: **only committed + pushed work survives.**
> Keep this current before stopping or switching context. Updated **2026-06-15**.

iplan-runner is the **public OSS IPLAN executor** (MIT; pre-1.0, `v0.14.0`). All
Phase-D design is done + ratified; the next work here is the **D-4b BUILD**.

## Recently merged on `main`

- **Public OSS migration (PLAN-018):** relicensed Apache-2.0 → MIT, community-health
  files, Actions SHA-pinned + gitleaks checksum, path-leak/private-disclosure
  curation (G8), history squashed, repo flipped **public**.
- **Versioning corrected to pre-1.0 (`0.14.0`):** the contract still evolves
  (Phase-D), so `0.x` is honest; `1.0.0` is reserved for GA / contract-freeze.
  Spec-version parity holds across `framework/VERSION`, the registry
  `spec_version`, and both engine `FRAMEWORK_SPEC_VERSION`; engine packages are
  also `0.14.0`.
- **Governance single-sourced:** `GOVERNANCE.md` points to
  `aidoc-flow-framework/framework/governance/` (never copied).
- **Operating modes documented** (README + `TODO.md`/`ROADMAP.md`): standalone
  (offline) is the default; iplanic sync is a config toggle, off by default.
- Internal alias **`iplanner`** registered for iplan-runner (private brand
  registry only; not in this public repo).

## Repo state

- **`main`, clean, public.** Remote `https://github.com/vladm3105/iplan-runner`.
- Python packages are **`iplan_hermes` / `iplan_claude`** (renamed from `iops_*`).
- Already a **conformant Iplanic remote executor** (D-0016, transport-agnostic): it
  emits signed `execution-event`s in Iplanic's shape by projecting its own ledger
  (`platforms/<engine>/src/iplan_<engine>/ledger/events.py:to_execution_events`),
  signed by `security/iplanic_signing.py`. Conformance-proven (PLAN-013/014/015).
- Dual-engine **strict isolation** (D-0011): `hermes` + `claude` share no code, only
  `framework/` data; behavioral parity via golden vectors.

## What's pending here: D-4b (the BUILD of the D-4 transport)

The **design is merged**: `plans/PLAN-017_d4-iplanic-transport-design.md` + decision
**D-0020** (`plans/DECISIONS.md`). D-4b implements it. **Author a verified-planning
`PLAN-019` (D-4b) first, then build** (PLAN-018 is the public-migration plan — the
next free number is 019). The design already resolved the hard parts:

- **Ledger-relay / drain worker** (per-engine, no shared code): reads the durable
  ledger in append order → project (`to_execution_events`) → sign
  (`iplanic_signing.sign`) → `POST` to iplanic `/v1/events` **verbatim** (incl.
  placeholder `received_at = occurred_at`) → on `202`, advance a **durable cursor**.
- **⚠ Load-bearing implementation note:** the `idempotency_key`/`event_id` MUST
  anchor on the **D-0008 hash-chain identity** (`ledger/store.py:compute_event_hash`
  → `sequence`/`event_hash`), **NOT** the positional `IdSource` counter
  (`ledger/events.py:_build_event`, `event_id = ids("EV")`). Positional derivation
  makes re-projection produce different keys for the same event → defeats iplanic's
  `idempotency_key` dedup. A value-derivation change to the emit projection (wire
  field unchanged).
- **Config-gated sync toggle + on-demand sync** (the operating-modes feature): an
  `iplanic.sync` config block, **off by default** (standalone/offline); when on,
  the drain worker relays, and an on-demand command flushes the local ledger /
  logs / evidence from the cursor. See `TODO.md` "Operating modes & iplanic sync".
- **Reject → outcome map:** `202` → success/advance; `timestamp_skew` → classify
  **locally** (far-stale → dead-letter, else retry-with-cap);
  `invalid_signature`/`schema_invalid` → terminal+halt; registration/scope (403) →
  terminal+escalate → dead-letter; `401` → refresh token once → escalate;
  transport/5xx → retry-with-backoff.
- **Cursor + dead-letter both durable**; the cursor advances past a terminal reject
  **only after** a durable dead-letter commit (no silent loss).
- **Auth:** injected bearer-token provider seam (real OIDC deferred; static token in
  tests). **Integration suite:** in-process fake iplanic server (202 + reject
  envelope), gated/opt-in (PLAN-008 "not in CI" pattern); drift mitigated by the
  pinned `framework/remote/iplanic-vectors/`. Endpoint: iplanic `POST /v1/events` →
  `202 {event_id}` (idempotent replay) or `{reason, detail}` at 401/403/400; pinned
  `1.3-draft` (D-0018).

## Working protocol (this repo's specifics)

- **Verified-planning** is mandatory: cited Claim ledger + ≥2 passes incl. ≥1
  independent fresh-context `Agent` review, then
  `python .claude/skills/verified-planning/check_plan.py <plan>`.
- **Never merge** without the user's command. Branch + PR; the user merges and
  replies "merged and remote deleted" → then sync + prune.
- **Branch protection:** PRs need **1 approval** to merge.
- `git push` works over SSH; **`gh` needs `env -u GH_TOKEN`** (the ambient
  `GH_TOKEN` is stale; gh's stored github.com creds are valid).
- **CI gotchas:** (1) the **`pre-commit --all-files`** job ("Lint / format /
  security hooks") gates **every** plan — inserting/shifting lines in a file a plan
  cites breaks **other** gated plans' citations (refresh them all). (2)
  **PLAN-001..012 are grandfathered** out of the gate in pre-commit but **NOT** in
  CI `plan-gate.yml` — editing a 001..012 plan, or deleting/renaming a cited file,
  fails CI; mind the citations. (3) CodeQL ("Analyze Python") is slow — not a
  failure.
- Next **decision** = **D-0021**; next **plan** = **PLAN-019**. `plans/DECISIONS.md`
  is `### D-00NN` prose (D-0001..D-0013 ascending, then a newest-first block —
  insert new decisions at the **top of the newest block**).

## Sibling: iplanic (the standard + ingestion service)

The `aidoc-flow-iplanic` repo (private — planned public) — D-1/D-2 **built**;
D-3 design (PLAN-015, D-0034) merged; **D-3b** (the PostgreSQL build) is its
pending counterpart. iplanic owns the IPLAN lifecycle / versioning / dispatch /
completion gate / evidence system-of-record; iplan-runner is the executor that
relays signed events to it (when sync is on).
