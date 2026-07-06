# iplan-runner — Session Handoff

> Durable resume doc — the **canonical** handoff for this repo (per `CLAUDE.md`).
> Sessions run in ephemeral containers: **only committed + pushed work survives.**
> Keep this current before stopping or switching context. Updated **2026-06-27**.

iplan-runner is the **public OSS IPLAN executor** (MIT; pre-1.0, `v0.14.0`). The
**D-4 iplanic transport is fully built + merged**: **D-4b** (transport — PLAN-019, PR #40)
and **D-4c** (SQLite operational store — PLAN-020/D-0021, PR #42). Sibling-side, iplanic's
**D-3b PostgreSQL persistence is also merged (PR #50)**, so the full ingestion runtime is
live; the next ecosystem build is iplanic's **management API** (sibling repo).

**Consume the IPLAN standard (PLAN-023 / D-0023):** the standard now lives in its own OSS repo
[`iplan-standard`](https://github.com/vladm3105/aidoc-flow-iplan-standard) (`iplan/v0.1.0`); iplan-runner is a
**pinned consumer**, not a fork. The canonicalization/signing is vendored as `security/iplan_canonical/` per
engine (the standard's verbatim copy) with `security/iplanic_signing.py` a thin re-export shim; the
`framework/remote/` mirror is re-derived to the current shape; `sync/check-drift.sh` byte-diffs the vendored
surface against the pinned tag. **Do not edit the vendored package or fork the standard** — change upstream +
re-pin.

**Forward — IPLAN Assurance (design stage, 2026-06-27):** a cross-repo initiative to add
**verifiable provenance + transparency (NOT blockchain)** to IPLAN. Neutral contract drafted upstream:
`iplan-standard/docs/standards/IPLAN-ASSURANCE.md` (DRAFT — assurance levels L0 unsigned / L1 signed
initiator / L2 transparency-logged; `iplan-standard` PR #3). **Runner's part = the L1 intake provenance
gate:** verify an initiator signature over the canonical IPLAN against an authorized-initiator keyring
**before** execution (new `INTAKE.PROVENANCE_*` rules alongside `INTAKE-001`), reusing the vendored
`security/iplan_canonical/` signer and composing with — not replacing — D-0015 actor identity. Not yet a
PLAN; ratify L1 upstream first, then author the consumer plan here as a pinned consumer. Commercial
framing (out of this repo): `business/docs/STRATEGY_VERIFIABLE_AGENT_EXECUTION.md` (`business` PR #34).

## Recently built: D-5a inbound task receiver (PLAN-021 / D-0022)

The **inbound** half of the iplanic transport is built (both engines, D-0011): an
opt-in `POST /v1/tasks` receiver (`receiver/` — `auth`/`service`/`heartbeat`/`http`,
stdlib `http.server`, gated out of CI) accepts an iplanic A2A `task.schema.json`
dispatch under a **mandatory** bearer, ACKs `202` promptly, runs a **deterministic**
executor through intake → orchestrator → relay back to iplanic, stays dispatchable
via a heartbeat thread, and is idempotent on `(run_id, task_id)` (a new
`accepted_task` table: split durable-accept + atomic claim, so concurrent POSTs ACK
but exactly one runs). Adds the inbound contract section, an extended
`validate_payload` (`REMOTE.PAYLOAD_REPOSITORY_SHAPE`), `adapt_dispatched_task` +
`ingest_task_payload_dict`, a `receiver` config block + `server` CLI verb, a gated
end-to-end wire test, and a `reject_repository` conformance vector. **No iplanic PR
remains** (dispatcher-auth shipped, iplanic PLAN-048/D-0067) — only provisioning per
iplanic `docs/runbooks/EXECUTOR-DISPATCH-SETUP.md`. **Verified:** 256 offline + 12
gated tests (both engines), 26 conformance, ruff + `mypy --strict` clean.

**PLAN-022 (D-0024) SHIPPED (2026-07-05):** the receiver now **clones the dispatched
repository** `{url,base_ref}` into a per-run workspace (`vcs/git.clone` +
`receiver/service.provision_workspace`, `_slug` path-safe) and the executor is an
injectable `ReceiverDeps.make_executor` factory (default still `MockExecutor`). Both
engines.

**PLAN-023 (D-0025) SHIPPED (2026-07-05):** the receiver now **config-selects** its
executor (`receiver.executor`: `mock` default / `host` claude / `api` hermes) via the
seam. **Correction:** each engine already ships its OWN real-agent executor (claude
`HostRuntimeExecutor` over `RuntimeClient`; hermes `ApiExecutor` over `ModelClient`) —
it was never a parity gap; the wiring is *engine-specific* (D-0013), not byte-parallel,
and that's fine (spec parity = version + no-cross-import, not a source diff). Wired
with the **stub** clients (fully CI-able). **Deferred → PLAN-024:** the **real** client
adapters — claude's Claude Code hook `RuntimeClient` (unbuilt, integration-only) +
hermes's `get_model_client(...)` (`[anthropic]` extra + credentials) — a config-guarded
one-line swap. Still deferred: auto re-drain on outage, in-flight crash-recovery,
mTLS/OIDC inbound auth.

## Recently merged: D-4b iplanic transport (PLAN-019, PR #40)

The online + on-demand-sync operating modes are real:
- **Idempotency-key fix** (Task 1): `execution-event` `event_id`/`idempotency_key`/
  `trace_id` now anchor on the D-0008 `event_hash` (+ `event_type` discriminator for
  the `task.completed`+`test.*` fan-out), not the positional counter — re-projection
  is byte-stable. Projection golden regenerated; cross-engine differential re-proven.
- **Per-engine `relay/` package** (Task 2, byte-identical): `client.py` (HTTP POST,
  bearer-token seam, bounded retry), `reject.py` (reject→outcome classifier),
  `store.py` (durable settled-cursor + dead-letter + identity sidecar), `worker.py`
  (at-least-once drain; dead-letter commits before the cursor advances).
- **Config toggle + CLI `sync`** (Task 3): `iplanic.sync.enabled` (off by default);
  `iplan-<engine> sync` (`--payload`/`--dry-run`). A sync-disabled run opens no socket.
- **Gated fake-iplanic suite** (Task 4): `IPLAN_FAKE_IPLANIC=1`, 8 cases/engine, not in CI.
- Verified green: conformance 26, 226 offline + 16 gated tests, ruff/mypy/bandit clean.

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

## What's next here

- D-4b's + D-4c's **Out of scope** items (none blocking): full auth wiring (D-0015,
  OIDC/SPIFFE for the bearer seam); continuous/auto-sync daemon (today on-demand only);
  identity for identity-less standalone runs; iplanic-side ingestion = the sibling
  repo's **D-3b** build.

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
- Next **decision** = **D-0026**; next **plan** = **PLAN-024** (real client adapters:
  Claude Code hook `RuntimeClient` + hermes `get_model_client` wiring — integration-only;
  PLAN-019/020/021/022/023 DONE, D-0021/0022/0024/0025 used). `plans/DECISIONS.md`
  is `### D-00NN` prose (append new decisions at the **end** of the file).

## Sibling: iplanic (the standard + ingestion service)

The `aidoc-flow-iplanic` repo (private — planned public) — D-1/D-2 **built**;
D-3 design (PLAN-015, D-0034) merged; **D-3b** (the PostgreSQL build) is its
pending counterpart. iplanic owns the IPLAN lifecycle / versioning / dispatch /
completion gate / evidence system-of-record; iplan-runner is the executor that
relays signed events to it (when sync is on).
