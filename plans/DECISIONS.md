# Architecture Decisions

ISO-8601 stamped, append-only. Newest decisions reference and may supersede
older ones (mark superseded entries, never delete).

---

### D-0001 - Repo is a hybrid spec + runtime - 2026-05-23

`aidoc-flow-iops-framework` is a **hybrid**: an engine-agnostic *contract* in
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
