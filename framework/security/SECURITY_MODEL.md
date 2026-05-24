# Security Model

The framework's trust boundary: an **authenticated** ledger, **layered
authorization** over **agent-first** identity, a hardened sandbox, and the
principle that agent/tool **output is data, never instructions**.

## Authenticated ledger (HMAC)

The execution-log hash chain is tamper-*evident* (anyone can recompute
`event_hash`) but not *authenticated*. Signing makes it tamper-*proof* without
the key:

```
signature = "hmac-sha256:" + HMAC_SHA256(key, canonical(event))
canonical(event) = json.dumps(event without "signature", sort_keys=True,
                              separators=(",", ":"))
```

- The signature covers the **canonical JSON of the full event** (every field),
  not just `event_hash` — so a tamper of any field (`touched_paths`, `client_id`,
  …) is detected.
- `sign_ledger(ledger, key)` stamps every execution-log event; `verify_ledger(
  ledger, key)` re-verifies the chain **and** that every event carries a matching
  signature (a missing or wrong signature → invalid).
- The key is **injected** (`Config.signing_key` / env); never committed. Signing
  is a post-run step (e.g. `land()`), so unsigned runs are unchanged.

## Identity (agent-first, M2M / A2A) — forward-looking

IPLAN actors are **agents / machines** (engines, sub-agents, CI), not humans at a
browser. Identity is workload-identity- and delegation-first (full wiring is a
later phase; see D-0015):

- **Workload identity:** SPIFFE/SPIRE (SVID, mTLS, JWT-SVID) and/or OAuth2
  **client-credentials** — no static long-lived secrets.
- **A2A delegation:** OAuth2 **Token Exchange (RFC 8693)** (`act`/`may_act`),
  capability-scoped least-privilege tokens, bounded delegation depth; align with
  the **A2A protocol** + **MCP** client auth.
- Human **OIDC** login is reserved for the operator **approval/override** layer
  (HITL, PLAN-009).
- The verified `Principal` is agent-shaped: `{agent_id, role, capabilities,
  on_behalf_of, client_id, project_id}`. The acting agent + delegation chain is
  stamped into the ledger and signed.

## Authorization (layered, defense in depth)

A decision must pass **every** applicable layer, behind a pluggable `Authorizer`
PDP. PLAN-007 implements the inner layers (L1–L2); L0/L3/L4 are external engines
plugged into the same interface later (D-0015).

| Layer | Concern | Owner |
|-------|---------|-------|
| L0 Identity | which agent / on whose behalf | SPIFFE / OAuth2 client-creds |
| L1 Tenant | `client_id`/`project_id`/`allowed_roots` | framework (enforced) |
| L2 RBAC | agent role → action | framework (`authorize`) |
| L3 ReBAC | agent↔resource↔principal delegation graph | OpenFGA / SpiceDB |
| L4 ABAC/policy | capability scope, delegation depth, risk, budget | OPA / Cedar |

### RBAC (this phase)

`authorize(actor, action) -> {allowed, reason}` over a fixed role/action matrix:

| Role | run | record | edit | land | approve | override |
|------|-----|--------|------|------|---------|----------|
| `agent` | ✅ | ✅ | ✅ | — | — | — |
| `operator` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

Reason codes: `AUTHZ.OK`, `AUTHZ.ROLE_FORBIDDEN`, `AUTHZ.UNKNOWN_ROLE`. (These are
decision outputs, not document-`validate()` findings — like the sandbox codes.)

## Untrusted output (structural prompt-injection defense)

Agent/model/tool **output is data, never instructions.** The engine never
interprets free-form output as commands: actions are a typed `ExecutorResult` or
a pre-written script, effects are **sandboxed**, command output is **redacted**
for secrets. There is no instruction-following on untrusted content — the
strongest prompt-injection defense is structural, not a fragile heuristic.

## Sandbox hardening

`apply_write` enforces two checks before any write:

1. **Lexical** — `classify_path` (PLAN-004): deny absolute / `..`-escaping /
   out-of-roots (the parity surface).
2. **Realpath** — resolve the target's real path and the workspace root and
   reject if the real target escapes the workspace, so a **symlink** inside
   `allowed_roots` cannot redirect a write outside.

## Threat model

| Threat | Mitigation | Phase |
|--------|------------|-------|
| Tampered ledger evidence | hash chain (evident) + HMAC signature (authenticated) | 1 / 7 |
| Edit/command escapes the workspace | sandbox lexical + realpath; gate isolation rules | 4 / 7 |
| Secrets leak into the ledger/logs | redaction before storage | 4 |
| Unauthorized actor runs/lands/overrides | layered authz (L1 tenant, L2 RBAC; L3/L4 external) | 7 / later |
| Prompt injection via tool/model output | output is data, never instructions (structural) | 7 |
| Over-broad delegation (A2A) | capability-scoped tokens + bounded delegation depth | later (D-0015) |
| Cross-tenant leakage | isolation scope + touched-path containment | 1 |
