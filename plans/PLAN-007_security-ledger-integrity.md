# Security & Ledger Integrity Implementation Plan

> Development plans follow the SDD workflow: **plan → review (≥2 passes) →
> implement → verify → land**. This plan must pass ≥2 review passes (see
> `## Review log`) and be approved before implementation begins.

**Goal:** Harden the framework's trust boundary (Roadmap Phase 7 → `v0.7.0`):
make the ledger **authenticated** (HMAC-signed, not just hash-chained), add a
**role-based authorization** decision (who may run / land / approve / override),
**harden the sandbox** against symlink escape, and write the **security model /
threat model**. Prompt-injection is addressed structurally (model/tool output is
**data, never instructions**).

**Architecture:** Additive (D-0014). New `framework/security/SECURITY_MODEL.md`
and two new conformance kinds (`signing/`, `authz/`). Two-regime parity (as
PLAN-004/006): the **keyed-pure** signing (HMAC, fixed test key) and the **pure**
authz decision are golden-vector'd + differential; **realpath** sandbox hardening
is real I/O, per-engine tested. The run loop is untouched — signing is a separate
`sign_ledger` step (default off, no key), so all prior scenarios stay green.

**Tech Stack:** Python ≥3.11 (`hmac`, `hashlib`, `pathlib`); `pytest`;
`unittest` conformance; `ruff` + `mypy --strict`; YAML.

---

| Field      | Value |
|------------|-------|
| Task       | IOPS-PLAN-007 |
| Depends on | `PLAN-001`..`PLAN-006` (DONE); D-0011..D-0014; Roadmap Phase 7 |
| Status     | DONE - 2026-05-24 |
| Feeds      | `PLAN-008` (live executors run under authz + sign their ledgers); `PLAN-009` (operator approval uses authz) |

## Objective

The hash chain is tamper-*evident* but not *authenticated* (anyone can
recompute it), nothing constrains *who* may act, and the sandbox is lexical
(symlinks can escape). PLAN-007 adds the security primitives:

1. **Authenticated ledger.** `sign_ledger(ledger, key)` stamps each execution-log
   event with `signature = "hmac-sha256:" + HMAC(key, canonical(event))`, where
   `canonical` is the event's sorted-key JSON **excluding** the `signature` field
   — so the signature authenticates **every** field (closing the gap that
   `event_hash` covers only `sequence|prev|event_type|subject_id|at`).
   `verify_ledger(ledger, key)` recomputes + checks the chain *and* every
   signature. An auditor with the key can prove the ledger is authentic, not just
   internally consistent.
2. **Authorization.** `authorize(actor, action) -> {allowed, reason}` over a role
   policy (`agent` may run/record/edit; `operator` may also land/approve/override).
3. **Sandbox hardening.** `apply_write` resolves `realpath` and rejects writes
   whose real target escapes the workspace (symlink defense), on top of the
   lexical `classify_path`.
4. **Security model + threat model** doc, incl. the untrusted-output principle.

## Scope

**In:**

1. `framework/security/SECURITY_MODEL.md` — authenticated ledger (HMAC scheme),
   authz role/action policy + reason codes (`AUTHZ.OK`, `AUTHZ.ROLE_FORBIDDEN`,
   `AUTHZ.UNKNOWN_ROLE`), the untrusted-output principle, sandbox hardening, and a
   threat-model table. Registry → add the doc + `signing_root`, `authz_root`.
2. Golden vectors: `framework/conformance/signing/<name>` (`{key, event}` →
   `{signature}`, fixed test key) and `framework/conformance/authz/<name>`
   (`{actor, action}` → `{allowed, reason}`).
3. Per engine (`hermes`, `claude`, independent): `security/signing.py`
   (`sign_event`, `sign_ledger`, `verify_ledger`), `security/authz.py`
   (`authorize`); `effectors/apply.py` realpath hardening; `Config.signing_key`
   (default `None`) + `secrets_from_env`; engine methods `sign_ledger`,
   `verify_ledger`, `authorize`; `land()` signs iff a key is configured; CLI
   `verify --key`; tests.
4. Conformance: `test_signing.py` + `test_authz.py` (cross-engine parity);
   registry path checks for the new roots.
5. Spec bump to `0.7.0`.

**Out:**

1. A full authentication system / identity provider / token verification — actor
   **identity** is host-provided; this phase authorizes a given actor (and the
   HMAC authenticates the *ledger artifact*). The recommended provider + layered
   authz model for the *eventual* integration is captured below and in D-0015.
2. Key management / rotation / a vault — the signing key is injected (config/env);
   storage is operator responsibility.
3. Heuristic prompt-injection *detection* — defended **structurally** (output is
   data, never instructions); content detection (if any) is Phase 8 with live
   executors.
4. Mandatory enforcement everywhere (e.g. refusing every unsigned/unauthorized
   run) — the primitives + opt-in wiring (`land` signs; authz available) land
   here; making them mandatory is incremental and must not break prior phases.

## Approach

**Signing is a separate step, not on the hot path.** `append_event` is
**unchanged**, so every prior ledger/scenario is byte-identical and all
conformance stays green. `sign_ledger(ledger, key)` is applied *after* a run
(e.g. by `land()` when a key is configured, or by the `sign`/`verify` CLI). With
the default `signing_key = None`, nothing signs and prior behavior is identical.

**Signing is keyed-pure → vector'd.** `sign_event(event, key)` is a
deterministic HMAC-SHA256 over the canonical JSON of the event. Golden vectors use a **fixed test key**, so both
engines compute identical signatures (differential) that match a pre-computed
expectation. `verify_ledger` is sign-and-compare. Because verification needs the
key, it is **not** a keyless `validate()` rule — it is a keyed function with its
own conformance, exactly like `classify_path`/`can_acquire`.

**Authz is a pure decision → vector'd.** `authorize(actor, action)` maps a role
+ action to allow/deny via a fixed policy matrix (each engine's own copy, kept
identical by vectors). It is a **primitive + decision point**, not forced into
`run()` (which has no actor) — so prior runs are unaffected. `land()` may take an
optional `actor` and check `authorize(actor, "land")`, defaulting to allow when
no actor is supplied (backward compatible).

**Sandbox hardening is real I/O → per-engine.** `apply_write` adds a
`realpath`-based containment check (resolve the target and the workspace, reject
if the real target is outside) so a symlink inside `allowed_roots` can't redirect
a write out of the workspace. Tested per-engine with a real symlink; the lexical
`classify_path` parity surface is unchanged.

**Prompt-injection is structural.** The engine never interprets executor/model
*output* as instructions — actions are a typed `ExecutorResult` / a pre-written
script, effects are sandboxed, output is redacted. The threat model documents
this; no fragile content heuristic is added here.

## File Structure

| Path | Responsibility |
|------|----------------|
| `framework/security/SECURITY_MODEL.md` | Authenticated-ledger scheme, authz policy + reason codes, untrusted-output principle, sandbox hardening, threat-model table. |
| `framework/conformance/signing/<name>/{input,expect}.yaml` | `{key, event}` → `{signature}` over canonical JSON (fixed test key). |
| `framework/conformance/authz/<name>/{input,expect}.yaml` | `{actor, action}` → `{allowed, reason}`. |
| `framework/registry/EXECUTION_REGISTRY.yaml` | + `SECURITY_MODEL.md`, `signing_root`, `authz_root`. |
| `platforms/<engine>/src/iops_<engine>/security/signing.py` | `sign_event`, `sign_ledger`, `verify_ledger`. |
| `platforms/<engine>/src/iops_<engine>/security/authz.py` | `authorize` + role/action policy + reason codes. |
| `platforms/<engine>/src/iops_<engine>/effectors/apply.py` | + realpath containment. |
| `platforms/<engine>/src/iops_<engine>/config.py` | `signing_key` (default None) + `secrets_from_env`. |
| `platforms/<engine>/src/iops_<engine>/engine.py` | `sign_ledger`, `verify_ledger`, `authorize`; `land(actor=None)` signs iff key. |
| `platforms/<engine>/src/iops_<engine>/cli/commands.py` | `verify --key`. |
| `platforms/<engine>/tests/test_security.py` | Signing round-trip + tamper, authz, realpath symlink escape. |
| `tests/conformance/test_signing.py` | Cross-engine `sign_event` parity. |
| `tests/conformance/test_authz.py` | Cross-engine `authorize` parity. |

## Step Sequence

### Task 1: Framework security model

- [ ] **Step 1:** `SECURITY_MODEL.md` — HMAC scheme (`signature = "hmac-sha256:"
  + HMAC_SHA256(key, canonical_json(event without signature))`, sorted keys),
  authz role/action matrix + reason codes, untrusted-output principle, realpath
  hardening, threat-model table.
- [ ] **Step 2:** registry — add the doc + `signing_root:
  framework/conformance/signing`, `authz_root: framework/conformance/authz`.
- [ ] **Step 3: commit** — `feat: add security model`.

### Task 2: Signing + authz vectors

- [ ] **Step 1:** signing vectors (fixed test key `"test-key"`): `basic`
  (a known event dict → its HMAC over the canonical JSON) and `tampered`
  (the same event with one field changed → a different signature). Expected
  signatures pre-computed with stdlib `hmac` over the canonical JSON.
- [ ] **Step 2:** authz vectors: `agent_run` (allow), `agent_land` (forbidden),
  `operator_land` (allow), `unknown_role` (unknown).
- [ ] **Step 3: commit** — `test: add signing + authz vectors`.

### Task 3: Hermes implementation (TDD)

- [ ] **Step 1: failing tests** — `sign_event` matches vectors; `sign_ledger`
  + `verify_ledger` round-trip; a tampered event/signature → `verify_ledger`
  false; `authorize` over the matrix; `apply_write` rejects a symlink escaping the
  workspace. Fail.
- [ ] **Step 2: `security/signing.py`** — `sign_event(event, key)` (HMAC over
  canonical JSON excluding `signature`), `sign_ledger(ledger, key)` (set each
  event `signature`), `verify_ledger(ledger, key)` (verify the chain + that every
  event's signature recomputes; a missing/wrong signature → false).
- [ ] **Step 3: `security/authz.py`** — policy matrix + `authorize`.
- [ ] **Step 4: `effectors/apply.py`** — add realpath containment after the
  lexical check.
- [ ] **Step 5: `config.py`** — `signing_key: str | None = None`;
  `secrets_from_env(prefix)` helper.
- [ ] **Step 6: `engine.py`** — `sign_ledger`/`verify_ledger`/`authorize`;
  `land(..., actor=None)` authorizes (if actor) and signs iff `signing_key`.
- [ ] **Step 7: `cli/commands.py`** — `verify <ledger> --key`.
- [ ] **Step 8: green** — `pytest`, `ruff`, `mypy --strict`. Commit
  `feat: add security (signing/authz/realpath) to hermes`.

### Task 4: Claude implementation (independent)

- [ ] **Step 1–7:** mirror Task 3 as an independent copy. No import of `iops_hermes`.
- [ ] **Step 8: green** + commit `feat: add security (signing/authz/realpath) to claude`.

### Task 5: Conformance

- [ ] **Step 1:** `test_signing.py` — cross-engine `sign_event` parity over
  signing vectors.
- [ ] **Step 2:** `test_authz.py` — cross-engine `authorize` parity over authz
  vectors; extend `test_registry` path checks to `signing_root`/`authz_root`.
- [ ] **Step 3: run full suite** + commit `test: add signing/authz conformance`.

### Task 6: Version bump, changelog, handoff

- [ ] **Step 1:** atomic bump to `0.7.0`.
- [ ] **Step 2:** `CHANGELOG.md` `[0.7.0]`; update `HANDOFF.md`; plan `DONE`.
- [ ] **Step 3: full verification** + commit `chore: release spec v0.7.0
  (security & ledger integrity)`.

## Verification

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
```

Expected:

1. Conformance green: signing + authz decisions match `expect` in each engine +
   agree (differential); all prior checks unchanged at `0.7.0`.
2. Per-engine tests: `sign_ledger`/`verify_ledger` round-trip + tamper detection;
   `authorize` matrix; `apply_write` blocks a symlink escape.
3. `ruff` + `mypy --strict` clean.

## Auth / identity provider recommendation (forward-looking, agent-first)

IPLAN is an **agent-first** framework: the actors are agents / machines (the
engines themselves, sub-agents, CI runners) acting **A2A** (agent-to-agent) and
**M2M** (machine-to-machine) — *not* humans logging in through a browser. So the
auth model is **workload-identity- and delegation-first**, with human OIDC login
reserved for the operator **approval/override** layer (HITL, PLAN-009). Full
authn is out of scope for this phase, but the direction is set now so the
PLAN-007 primitives (`authorize`, the actor role) slot in. Principles (matching
the vendor-neutral ethos of D-0011/D-0013/D-0006):

1. **Identity = workload identity, not human login.** Prefer **SPIFFE/SPIRE**
   (short-lived SVIDs — X.509 for **mTLS**, JWT-SVID) as the agent/engine identity
   backbone (no shared long-lived secrets), and/or **OAuth2 client-credentials**
   (RFC 6749) for M2M tokens. The framework verifies the credential and extracts
   a `Principal` (`{agent_id, capabilities, on_behalf_of, client_id, project_id}`).
2. **A2A delegation is explicit.** When agent A acts on behalf of principal P (or
   agent B), use **OAuth2 Token Exchange (RFC 8693)** with the `act` / `may_act`
   (actor) claim, **capability-scoped** least-privilege tokens, and a bounded
   **delegation depth**. Align with the **A2A protocol** (Linux Foundation
   Agent2Agent) auth schemes and **MCP** client auth where engines expose/consume
   those surfaces.
3. **Authorization is layered (defense in depth)** behind a pluggable `Authorizer`
   PDP; a decision must pass **every** applicable layer:

| Layer | Concern (agent-first) | Owned by |
|-------|------------------------|----------|
| **L0 Identity** | which **agent/workload** (SVID / M2M token), and on whose behalf | SPIFFE/SPIRE or OAuth2 client-creds; framework verifies |
| **L1 Tenant** | `client_id` / `project_id` / `allowed_roots` boundary | Framework (already enforced) |
| **L2 RBAC** | agent role → permitted action (run/land/approve/override) | Framework (`authorize`, this plan) |
| **L3 ReBAC** | which agent may act on which IPLAN/ledger, incl. **delegation graph** | External authz engine |
| **L4 ABAC / policy** | context (capability scope, **delegation depth**, risk, budget, approval thresholds) | Policy-as-code engine |

### Recommended providers (agent-first ordering)

- **Workload/agent identity → SPIFFE/SPIRE** (primary): SVID issuance, mTLS,
  JWT-SVID — the standard for M2M/A2A identity without static secrets.
- **M2M tokens + delegation → Keycloak or Ory Hydra** (open-source): OAuth2
  **client-credentials** + **token exchange (RFC 8693)** + roles. Keycloak also
  bundles fine-grained Authorization Services (L2–L4). Managed: Auth0/Okta
  (client-creds + token vault / FGA), AWS Cognito, Azure Entra ID (workload IDs).
- **L3 ReBAC at scale → OpenFGA or SpiceDB** (Google Zanzibar): models
  agent ↔ resource ↔ principal **delegation relationships** directly.
- **L4 policy-as-code → OPA (Rego) or AWS Cedar**: capability/delegation-depth
  limits, budget caps, approval thresholds.
- **Human operator** (approval/override, PLAN-009) → any **OIDC** IdP — the
  *only* place a human login flow belongs.

### Framework seam

Add (in the authn integration phase, not now) an `Authorizer` Protocol (the PDP)
and a verified **agent** `Principal` (with `on_behalf_of` / capabilities); the
built-in RBAC `authorize` is the **default** Authorizer (inner layers L1–L2), and
external engines (SPIFFE-aware, OPA / OpenFGA / Keycloak adapters) implement the
same interface for L0/L3/L4 — the pluggability pattern of engines (D-0013) and
monitoring exporters (D-0006). Authz is evaluated at each decision point
(run / record / land / approve / override), and the acting agent (+ delegation
chain) is stamped into the ledger lease/transaction and signed (HMAC).

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Signing on the hot path would change every ledger/scenario. | `append_event` unchanged; `sign_ledger` is a separate post-step; default `signing_key=None` → no signing → prior phases byte-identical. |
| R2 | HMAC verification needs the key, so it can't be a keyless `validate()` rule. | Signing/verify are keyed functions with their own conformance (fixed test key), like `classify_path`/`can_acquire` — not document-validator rules. |
| R3 | Forcing authz into `run()` breaks prior tests (no actor). | Authz is a primitive + optional `land(actor=...)` check, default-allow without an actor; not wired into `run()`. |
| R4 | Realpath hardening is real I/O → not vector'd. | Lexical `classify_path` stays the parity surface (vector'd); realpath is per-engine tested with a real symlink. |
| R5 | A signing key committed/hardcoded. | Key is injected via `Config.signing_key` / env (`secrets_from_env`); vectors use an obvious fake `"test-key"`; no real key in the repo. |
| R6 | Over-promising on prompt-injection. | Scoped to the **structural** guarantee (output is data, never instructions) + redaction/sandbox; documented, no fragile detector. |
| R7 | Key management / rotation expectations. | Explicitly out of scope; documented as operator responsibility. |

## Review log

> ≥2 passes before implementation.

### Pass 1 - 2026-05-24

- Finding (substantive): signing over `event_hash` would only authenticate the
  hashed fields (`sequence|prev|event_type|subject_id|at`) — a tamper of
  `touched_paths`/`client_id`/`project_id` (not in the hash) would go undetected.
  Change: sign over the **canonical JSON of the full event** (sorted keys,
  excluding `signature`), so the HMAC authenticates every field. Updated
  objective, scheme, functions (`sign_event(event, key)`), and vectors.
- Finding: `verify_ledger` must reject a *missing* signature, not only a wrong
  one. Stated: every event must carry a valid signature, else false.
- Finding: HMAC verification needs the key, so it cannot be a keyless
  `validate()` rule. Confirmed: signing/verify are keyed functions with their own
  conformance (fixed test key), not document-validator rules (R2).
- Finding: forcing authz/signing into the hot path would break prior phases.
  Confirmed: `append_event` unchanged; `sign_ledger` is a post-step (default no
  key); authz is a primitive + optional `land(actor=...)` (default-allow) (R1, R3).

### Pass 2 - 2026-05-24

- Finding: cross-engine signature parity requires identical canonicalization.
  Stated: `json.dumps(sort_keys=True, separators=(",", ":"))` in both engines, so
  HMACs match (differential) — the canonical form is part of the contract.
- Finding: realpath hardening must not create files outside the workspace while
  checking. Resolved: resolve the deepest existing ancestor + the workspace and
  assert containment **before** `mkdir`/write; per-engine tested with a real
  symlink (R4).
- Finding: a committed/hardcoded key would be a leak. Confirmed: key injected via
  `Config.signing_key`/env; vectors use an obvious `"test-key"`; no real key in
  the repo (R5).
- Verification ↔ surface cross-check: keyed-pure signing + pure authz are
  vector'd + differential; realpath is per-engine (symlink escape); the run loop
  and all prior scenarios are untouched. No further findings.
