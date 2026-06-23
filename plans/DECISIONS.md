# Architecture Decisions

ISO-8601 stamped, append-only. Newest decisions reference and may supersede
older ones (mark superseded entries, never delete).

---

### D-0001 - Repo is a hybrid spec + runtime - 2026-05-23

`iplan-runner` is a **hybrid**: an engine-agnostic *contract* in
`framework/` (portable YAML + Markdown, no code) plus *reference runtimes* in
`platforms/` (real code), with a shared conformance suite in `tests/`. This
mirrors `aidoc-flow-framework` so we inherit "the same development approach."

### D-0002 - This repo is the execution/operations plane - 2026-05-23

SDD (`aidoc-flow-framework`) owns the **control plane**: BRD → … → IPLAN,
"done when committed + green." This framework owns the **execution/operations
plane** that begins at SDD's `EXEC-Ready (≥90)` gate: it consumes an approved
IPLAN and runs **IPLAN → Ledger → Gate → Monitor** (plan → append-only
execution evidence → independent completion proof → post-implementation
observation).

### D-0003 - Re-home the attached ledger plan under `framework/execution/` - 2026-05-23

The attached "IPLAN Ledger Implementation Plan" was authored against SDD's own
paths (`framework/layers/08_IPLAN/`, `platforms/hermes/...`,
`tests/conformance/`). We re-home its contract into `framework/execution/`
(not `framework/layers/08_IPLAN/`) because this repo is the *companion* to
SDD's Layer 8, not a re-declaration of it. A ledger binds to its source IPLAN
by `id` + `version` + `checksum`; we do **not** vendor SDD's IPLAN template and
take **no** hard dependency on the SDD repo.

### D-0004 - Development workflow mirrors SDD - 2026-05-23

Plan → review (≥2 passes) → implement → verify → land. Plans live in `plans/`
(start from `plans/PLAN-TEMPLATE.md`). Conformance must stay green; never weaken
a check to make it pass. One logical change per commit, conventional prefix.

### D-0005 - Per-engine platforms - 2026-05-23

`platforms/` holds one runtime per AI execution engine: `platforms/hermes/`
(MCP-server engine), `platforms/claude/` (Claude Code engine), and later
`platforms/codex/`, `platforms/vertexai/`, … All implement the same
engine-agnostic contract. **Slice 1 (PLAN-001) implements `hermes` + `claude`
fully**; other engines are follow-up plans.

### D-0006 - Monitoring is OpenTelemetry-based - 2026-05-23

Post-implementation monitoring uses OpenTelemetry (traces + metrics + logs via
OTLP) — exporter-agnostic, no vendor lock-in. `framework/monitoring/` defines
the manifest/SLO/signal contract; the runtime wires the OTel SDK and evaluates
SLOs. Health/readiness/startup probe shapes are adapted from the legacy
`aiops_framework` Cloud Run sample.

### D-0007 - [SUPERSEDED by D-0011] Shared `core/` library; relaxed isolation - 2026-05-23

> **Superseded 2026-05-23 by D-0011.** Originally proposed a shared `core/`
> (`iops_core`) library with a relaxed engine-isolation rule. Rejected by the
> repo owner in favor of SDD-faithful strict isolation; behavioral parity is
> instead guaranteed by golden conformance vectors (D-0012). Retained for
> history.

Original text: introduce a top-level `core/` package holding engine-agnostic
ledger/validation/gate/audit/monitoring logic that both engines import, relaxing
SDD's "platforms share only the spec" rule. Not adopted.

### D-0008 - Append-only, hash-chained, isolation-scoped ledger - 2026-05-23

The execution ledger is append-only; corrections are new compensating
transactions. The execution log is hash-chained (`sequence` +
`previous_event_hash` + `event_hash`). Every transaction is bound to an
isolation scope (`client_id` / `project_id` / `task_id`) and touched paths must
fall inside declared `allowed_roots`. Task transactions follow Saga-lite
semantics (forward action, compensation, idempotency key, timeout, escalation).
Inherited from the attached plan.

### D-0009 - Validation codes: coarse categories + fine-grained rule IDs - 2026-05-23

Keep the attached plan's **coarse categories**: `IPLAN-007` (ledger),
`IPLAN-008` (chain ledger), `IPLAN-009` (audit report), plus `MON-001`
(monitoring manifest) and `ENG-001` (engine-adapter conformance). **Add
fine-grained, stable rule IDs** beneath them (e.g. `LEDGER.EVIDENCE_REQUIRED`,
`LEDGER.LEASE_OVERLAP`, `CHAIN.UPSTREAM_UNRECONCILED`, `AUDIT.IDENTITY_MISMATCH`,
`HASHCHAIN.BROKEN`, `ISOLATION.PATH_OUTSIDE_ROOTS`, `MON.SLO_MISSING_TARGET`).

Rule IDs are enumerated canonically in `framework/conformance/rule-ids.yaml`
(documented in `RULE-IDS.md`); every engine validator must emit them per
finding. They are the unit of behavioral parity (D-0012) — coarse codes alone
are too imprecise to prove two engines agree. Validators stay deterministic
(dict-shape + regex), no LLM, no I/O — pure functions over parsed data.

### D-0010 - Python 3.11+ runtime - 2026-05-23

The container ships Python 3.11.15. Target Python ≥3.11 (SDD's Hermes targets
≥3.12, but the validator code uses only `dict[str,...]` / `list[...]` builtin
generics available in 3.11). Each platform declares `FRAMEWORK_SPEC_VERSION`
equal to `framework/VERSION`, enforced by conformance.

### D-0011 - Strict engine isolation, SDD-faithful - 2026-05-23

Supersedes D-0007. There is **no shared runtime library**. Each engine
(`platforms/hermes`, `platforms/claude`, …) is **fully self-contained**: it owns
its own ledger store, hash-chain, isolation enforcement, validators, gate runner,
audit generator, monitoring wiring, and CLI. Platforms share **only** the
`framework/` spec (templates, protocol docs, registry, rule-ID catalog, golden
vectors). Conformance enforces that no engine imports another engine's package.
Code duplication across engines is **intentional**, and is held safe by the
behavioral-parity mechanism in D-0012. Rationale: the repo owner wants the same
isolation guarantees SDD enforces, so engines can evolve (and be implemented in
different languages) independently while remaining interchangeable.

### D-0012 - Behavioral parity via golden conformance vectors - 2026-05-23

Because engines duplicate logic (D-0011), behavioral identity is guaranteed by
**golden conformance vectors**, not by shared code. `framework/conformance/`
ships language-neutral input documents paired with expected outcomes
(`*.expect.yaml`: `status` + the set of fine-grained `rule_ids`; severity is a
fixed catalog property checked separately against each emitted finding; human
message text is **not** compared). `tests/conformance/` replays every
vector against **every** engine (via each engine's uniform
`validate(document) -> {status, findings:[{rule_id, severity, ...}]}` entry
point) and asserts the rule-ID set + status match the expectation. Coverage is
cross-checked against `rule-ids.yaml` (every catalog rule has ≥1 vector; every
emitted/expected rule is in the catalog). The vector corpus is seeded from the
attached plan's Task 5 test cases. Ground truth lives in the spec, so a *single*
new engine can be certified against the spec alone (no need for other engines to
be present). Once ≥2 engines exist, an additional **cross-engine differential**
test asserts the engines agree with each other on every vector, as
defense-in-depth on top of the golden expectations.

### D-0013 - Execution = governance loop + pluggable executor - 2026-05-23

An execution engine is a **governance loop** (IPLAN ingestion → orchestrate →
execute → record ledger → gate → reconcile → monitor) wired to a pluggable
**`Executor`** interface. This dissolves the "autonomous coder (A)" vs
"governor/driver of a host runtime (B)" fork: the expensive, parity-critical
core (orchestrator, state machine, ledger writes, gate veto, saga, leases) is
written once per engine and is **executor-agnostic**, while *how a task gets
done* is a plug:

- `MockExecutor` — deterministic, for tests + scenario-vector conformance (no
  network);
- `HostRuntimeExecutor` — drives a host agent runtime (Claude Code, Codex, an
  MCP loop) — the "governor" style (B);
- `ApiExecutor` — calls a model directly — the "autonomous" style (A).

The A/B choice is therefore made **per executor plugin, per engine** (Phase 5),
not globally. Rationale: avoid rebuilding a coding agent per engine, keep the
whole loop testable offline via the mock plugin, and keep strict isolation
(D-0011) tractable — each engine duplicates a *small* driver, not a whole agent.
Stateful execution parity uses **scenario vectors** (op-sequence + mock executor
→ expected ledger), an extension of D-0012's pure-function golden vectors.

### D-0021 - SQLite for executor operational state; the signed ledger stays a portable file - 2026-06-15

The executor has **two storage roles with opposite requirements**, and they get
different engines:

1. **Evidence store** — the append-only, hash-chained, signed ledger + handover
   receipt. Its integrity comes from the chain + signatures (D-0008, D-0017), and
   its value as audit evidence is that it is a **portable file anyone can re-verify
   offline with no runtime**. It **stays file-based** (`ledger/persistence.py`,
   YAML). Not moved into a DB.
2. **Operational state** — the relay's settled-cursor, dead-letter, and persisted
   iplanic identity (today JSON sidecars in `relay/store.py`). This wants
   transactions, an index, and concurrency-safety. It moves to **SQLite** (D-4c,
   PLAN-020).

**Why SQLite specifically:** it is **Python stdlib (`sqlite3`) — no new dependency**
(deps stay `pyyaml`/`rfc8785`/`cryptography`), single-file, serverless. So it keeps
the standing "standalone runs with zero external dependencies" guarantee and the
air-gapped / Claude-plugin use cases intact. **Postgres is rejected for offline**
(a server dependency defeats standalone/air-gap/plugin); Postgres stays iplanic's
control-plane engine — the two planes are deliberately **not** symmetric in
infrastructure.

**Sync-friendly with iplanic (the load-bearing design rule):** the operational
schema is an **outbox keyed on the stable `idempotency_key`** — the *same* key
iplanic dedups on (D-4b, anchored on the D-0008 `event_hash`). One row per projected
event records `delivered`/`dead_lettered`; the drain becomes "events whose key has no
row → POST → write row." This **collapses the D-4b two-write invariant**
(dead-letter commit *then* cursor advance) into **one atomic transaction** (the
dead-letter row *is* the cursor mark), removing the crash-window that today can
double-write a dead-letter entry. The shape **mirrors iplanic's own transactional
outbox** (its D-3b ingestion), so at-least-once delivery is reasoned about
identically on both ends.

**Scope:** per-engine (D-0011, no shared code); `relay/store.py` is re-implemented
over `sqlite3` behind its **current public interface** (so `relay/worker.py` and the
CLI `sync` are unchanged and the gated suite regresses it). The run index/status
(`ledger/index.py`, which globs the ledger files) is **out of scope** — it reads the
file ledgers, which stay. Pre-1.0, so **no back-compat migration** of existing JSON
sidecars.

### D-0020 - Iplanic transport: ledger-relay → `POST /v1/events` (design) - 2026-06-14

Design the iplan-runner-side **transport** (PLAN-017) that delivers signed
`execution-event`s to Iplanic's `POST /v1/events` — **design/spec only, no
implementation** (the build is D-4b). A **ledger-relay / drain worker** reads the durable
ledger in append order, projects each event to Iplanic shape (`to_execution_events`),
signs it (`iplanic_signing.sign`), and POSTs it **verbatim** (incl. the placeholder
`received_at = occurred_at`, which Iplanic overwrites and excludes from the signature),
advancing a **durable cursor** (at-least-once; the cursor advances only on `202`). That
dedup **requires** anchoring the `idempotency_key` on the **D-0008 hash-chain identity**
(`sequence`/`event_hash`) — the current positional `IdSource` counter is insufficient (a
D-4b value-derivation change, not a wire-shape change). Reject→outcome map:
`timestamp_skew` is **not** server-distinguishable, so the relay classifies locally
(heuristic); `invalid_signature`/`schema_invalid` → terminal+halt; registration/scope
codes → terminal+escalate → **dead-letter** (durable; the cursor advances only after a
durable dead-letter commit — no silent loss); transport faults → retry-with-backoff.
**Per-engine** (D-0011, no shared code); an **in-process fake Iplanic server** backs the
gated, integration-only suite (PLAN-008 "opt-in, not in CI" pattern). Builds on the
transport-agnostic remote-executor contract (D-0016) and the pinned Iplanic `1.3-draft`
endpoint (D-0018).

### D-0019 - Drop the former engineering codename; rename packages `iops_*` → `iplan_*` - 2026-06-14

`iplan-runner` drops its former engineering codename, and its Python packages
drop the `iops_` brand: `iops_hermes` → `iplan_hermes`, `iops_claude` →
`iplan_claude`. The distribution names become `iplan-hermes` / `iplan-claude`,
and the CLI entry points become `iplan-hermes` / `iplan-claude`. The package
keys in `framework/registry/EXECUTION_REGISTRY.yaml` are updated in lockstep so
the conformance loader resolves both engines after the rename. Engine identities
`hermes` / `claude` are unchanged, and the contract, the golden vectors, and the
Iplanic wire surface are all unchanged — this is a rename only, with no
behavioral or schema impact, and no migration is required for existing ledgers.
This decision **supersedes** the codename annotation in D-0001. Historical
references in the grandfathered plans (PLAN-001..012), which predate the
verified-planning gate, are intentionally left as-is rather than rewritten to
match the new package names.

### D-0018 - Re-pin Iplanic mirrors to `1.3-draft`; enforce the `executor_id` hash form - 2026-06-11

Iplanic shipped its first breaking change (PLAN-012 / D-0031): `executor_id` is
tightened to `^exec:[a-z2-7]{16,}$` (`exec:<base32(sha256(...))>`, §2.1) and the
schema set is bumped `1.2-draft → 1.3-draft` (commit `fb5f46d`). IOPS pins by commit,
so its CI stayed green until this deliberate re-pin.

- **Advance the pin** (SOURCE.md + the two `framework/remote/` template headers + the
  IPLAN-ECOSYSTEM comparison table) from `bf3b9b6`/`1.2-draft` to `fb5f46d`/`1.3-draft`.
  The vendored canonicalization vectors are **byte-identical** (Iplanic exempted the
  canon goldens, which keep `exec:abc`), so the signing contract is untouched.
- **Conform the value:** rewrite IOPS's non-conforming `exec:remote` to the hash form
  across the accept payload/template/tests and **regenerate** the golden event
  signatures (`executor_id` is in the signed canonical payload).
- **Enforce the form:** add `REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT` — a payload whose
  `executor_id` is present but not the hash form is rejected at intake, mirrored
  across both engines (D-0011) with a `reject_executor_id` conformance vector. The
  reject conformance test now discovers all `reject_*` vectors. Without this, IOPS
  would carry a malformed `executor_id` into a signed, emitted event Iplanic rejects.
- Additive rule → framework `MINOR` bump `1.1.0 → 1.2.0` (VERSION + registry
  `spec_version` + both `FRAMEWORK_SPEC_VERSION` markers, parity-gated); engines
  `0.12.0 → 0.13.0`.

### D-0017 - Adopt `iplan-canonical-json` for Iplanic event signing - 2026-06-11

Iplanic-emitted `execution-event` signatures must be **byte-reproducible by
Iplanic**, so IOPS adopts Iplanic's normative `iplan-canonical-json` (RFC 8785 JCS
over `sha256` with recursive drop-null; signed payload excludes `{signature,
received_at}`; HMAC keyed with **raw bytes**; `ed25519` as well as `hmac-sha256`;
`value` lowercase hex) for the Iplanic-emission path — a new
`security/iplanic_signing.py`, copied identically into each engine (D-0011).

The legacy authenticated-ledger signer (`security/signing.py` `sign_event` /
hash-chain) is **retained unchanged** for the standalone ledger; it HMACs IOPS's
own `json.dumps` canonical and is **not** byte-reproducible by Iplanic (proven
against Iplanic's golden `sig_hmac` vector). Conformance vendors Iplanic's golden
vectors (`framework/remote/iplanic-vectors/`, version-pinned) and reproduces them
byte-for-byte. `sign` returns the hex `value`; the consumer assembles the event
`signature` object. PLAN-013's event emission consumes this signer. (PLAN-014.)

### D-0016 - Additive Iplanic remote-executor contract (vendored, transport-agnostic) - 2026-06-11

IOPS becomes a **conformant remote executor for Iplanic** additively: a second
intake front door (`ingest_task_payload`) maps Iplanic's task payload to the same
`iplan-intake` manifest the run loop already consumes, and event emission
(`to_execution_events`) projects the existing signed ledger into Iplanic's
`execution-event` shape. The standalone run loop, ledger, gate, saga, and evidence
runner are **unchanged**.

Iplanic's schemas are **never imported**: the consumed payload subset and the
emitted event required-field list are **vendored, version-pinned mirrors** under
`framework/remote/` (drift surfaces as a failing conformance vector, not a runtime
dependency). Emission is **offline / in-memory**; a live HTTP POST to Iplanic
ingestion is integration-only (PLAN-008 boundary). Signing uses the
`iplan-canonical-json` signer (D-0017). The sandbox `classify_path` gains an
optional `forbidden_paths` arg + `SANDBOX.FORBIDDEN` reason (checked after the
positive jail; existing callers unchanged). New rule category `REMOTE-001` with
`REMOTE.PAYLOAD_*`. (PLAN-013.)

### D-0015 - Auth: agent-first (M2M/A2A) identity + pluggable, layered authorization - 2026-05-24

IPLAN is **agent-first**: actors are agents/machines (engines, sub-agents, CI)
acting **A2A**/**M2M**, not humans at a browser. Identity and authorization are
**provider-agnostic and pluggable** (engine D-0013 / exporter D-0006 ethos), and
**workload-identity- and delegation-first**.

- **Identity (M2M/A2A, not human login):** prefer **SPIFFE/SPIRE** (short-lived
  SVIDs: X.509 mTLS + JWT-SVID) for agent/engine identity, and/or **OAuth2
  client-credentials** for M2M tokens. The framework verifies the credential and
  extracts an **agent** `Principal` (`{agent_id, capabilities, on_behalf_of,
  client_id, project_id}`). Human OIDC login is reserved for the operator
  **approval/override** layer (HITL, PLAN-009) — the only place it belongs.
- **A2A delegation is explicit:** **OAuth2 Token Exchange (RFC 8693)**
  (`act`/`may_act` actor claim), capability-scoped least-privilege tokens, bounded
  delegation depth; align with the **A2A protocol** (LF Agent2Agent) + **MCP**
  client auth.
- **Authz is layered (defense in depth)** behind a pluggable `Authorizer` PDP;
  a decision passes every applicable layer:
  - **L0 Identity** (which agent / on whose behalf) — SPIFFE or OAuth2 client-creds.
  - **L1 Tenant** (`client_id`/`project_id`/`allowed_roots`) — framework, enforced.
  - **L2 RBAC** (agent role → action) — framework (`authorize`, PLAN-007).
  - **L3 ReBAC** (agent↔resource↔principal **delegation graph**) — OpenFGA/SpiceDB.
  - **L4 ABAC/policy** (capability scope, delegation depth, risk, budget,
    approval thresholds) — OPA/Rego or Cedar.
- **Recommended (agent-first ordering):** SPIFFE/SPIRE for workload identity;
  **Keycloak** or **Ory Hydra** for OAuth2 client-credentials + token exchange
  (Keycloak also bundles fine-grained authz, L2–L4); OpenFGA/SpiceDB for L3;
  OPA/Cedar for L4. Managed: Auth0/Okta (+FGA), AWS Cognito + Verified
  Permissions (Cedar), Azure Entra ID (workload identities).
- Built-in RBAC `authorize` is the **default** `Authorizer`; external engines
  implement the same interface. The acting agent + delegation chain is stamped
  into the ledger and HMAC-signed. Full wiring is a later phase; PLAN-007 ships
  the inner-layer primitives. See `PLAN-007` "Auth / identity provider
  recommendation".

### D-0014 - Project structure conventions - 2026-05-23

Conventions for growing the repo across the roadmap, to keep additions purely
additive and churn-free:

1. **Sibling concern-dirs + registry discovery.** New contract surfaces are new
   `framework/<concern>/` directories; **every** artifact is listed in
   `framework/registry/EXECUTION_REGISTRY.yaml` so conformance discovers it by
   data, never by hard-coded path.
2. **One concern = one package, per engine.** Each engine grows by adding
   `src/iops_<engine>/<concern>/` packages (intake, orchestrator, executor,
   effectors, evidence, vcs, saga, leases, security, control, chain, …). Keep
   ledger persistence under `ledger/` (`store.py` + `persistence.py` + `index.py`).
3. **Injected clock + ID source.** Core logic (orchestrator/executor/ledger)
   takes time and identifiers as inputs — never ambient `datetime.now()` /
   `uuid4()`. Required so independent engines produce identical hash-chained
   ledgers under scenario vectors, and so everything is deterministically
   testable.
4. **`cli/` package from Phase 3.** When the CLI gains `run`/`status`/`pause`/…,
   `cli.py` becomes a `cli/` package with one module per command group.
5. **Stateless vs stateful vectors.** `framework/conformance/vectors/` holds
   pure-validator cases; `framework/conformance/scenarios/` holds stateful
   run-loop cases (`steps.yaml` + `expect.yaml`).

### D-0023 - Consume the IPLAN standard (vendor-pin + drift-check, replacing the stale fork) - 2026-06-23

The IPLAN standard now lives, versioned + OSS, in its own neutral repo
[`iplan-standard`](https://github.com/vladm3105/aidoc-flow-iplan-standard) (`iplan/v0.1.0`). iplan-runner
was consuming it three stale/hand-rolled ways: a vendored schema mirror pinned to an old iplanic commit
(`fb5f46d`/`1.3-draft`) that had drifted (`repository: "."` vs the live object — the bug PLAN-021's review
caught), and a **divergent parallel reimplementation** of the canonical-JSON + signing
(`security/iplanic_signing.py`, per engine). The "drift surfaces as a failing vector" promise never fired —
the vectors don't cover the payload shape. **Decision (PLAN-023):**

1. **Re-derive** the `framework/remote/` YAML subset from the pinned tag's `task.schema.json` (fixing the
   `repository`-object drift) + re-pin all provenance (`fb5f46d`/`1.3-draft` → `iplan/v0.1.0`). The mirror is
   a hand-derived *subset instance*, not byte-comparable to the JSON Schema — its correctness is the receiver
   adapter test, not a byte-diff.
2. **Vendor the standard's `iplan_canonical` as a package** (`security/iplan_canonical/`, a verbatim copy of
   the tag) in **each** engine (D-0011), and turn `security/iplanic_signing.py` into a **thin re-export shim**
   over it — preserving the public name + API, so every importer, `__all__`, and the conformance test are
   unchanged (zero rename blast radius). Hashes/signatures are now byte-identical to iplanic by construction
   (one source). `mypy --strict` over the verbatim *untyped* package is handled by **runner-local `.pyi`
   stubs** (mypy uses the stub interface + skips the untyped body; stubs aren't `*.py`, so they're invisible
   to the drift-check; runtime still loads the verbatim `.py`) + the shim's explicit `__all__`
   (`no_implicit_reexport`). [Refines the plan's "scoped mypy override", which couldn't fix the caller-side
   `no-untyped-call`.]
3. **`sync/check-drift.sh`** byte-diffs the byte-copyable surface (the vendored `iplan_canonical/` `*.py` per
   engine + the vector `*.json`) against the tag and **fails on drift** — replacing the non-functional drift
   claim. Vendor-pin (not a git dependency) keeps the OSS install self-contained.

**Deferred:** the held prose specs (`iplan/v0.2.0`); a package dependency. **Why:** iplan-runner consumed the
standard by stale hand-copies that silently forked; pinning every vendored artifact to the tag + a real,
scoped drift-check + one shared canonicalization source (behind the existing shim) makes drift structurally
impossible. Verified: conformance 26 + 244 offline tests green (the shim is behaviour-preserving), drift-check
in-sync + a negative test, ruff/mypy clean (no new errors).
