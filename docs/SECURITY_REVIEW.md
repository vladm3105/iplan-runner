# Security Review (v1.0.0)

This review walks the threat model in
[`framework/security/SECURITY_MODEL.md`](../framework/security/SECURITY_MODEL.md)
and, for each threat, names the **wired mitigation** and the **test that proves
it**. Residual / deferred items are listed explicitly — they are not hidden.

The framework's trust boundary is an **authenticated** ledger, **layered
authorization** over **agent-first** identity, a hardened **sandbox**, and the
principle that agent/tool **output is data, never instructions**.

## Threats, mitigations, and their tests

| Threat | Mitigation (wired) | Proof |
|--------|--------------------|-------|
| Tampered ledger evidence | Append-only hash chain (tamper-evident) + HMAC-SHA256 over the canonical full event (tamper-proof). `verify_ledger` re-verifies the chain **and** every event's signature. | `tests/conformance/test_signing.py` (signing vectors, cross-engine); `platforms/*/tests/test_security.py` (`sign_ledger`/`verify_ledger`); hash chain in `platforms/*/tests/test_integration.py` (`verify_chain`). |
| Edit/command escapes the workspace | `apply_write` enforces **lexical** `classify_path` (deny absolute / `..`-escape / out-of-roots) **and** a **realpath** check (a symlink inside `allowed_roots` cannot redirect outside). | `tests/conformance/test_sandbox.py` (path-jail decision parity); `platforms/*/tests/test_effectors.py` (sandbox-denied write); `platforms/*/tests/test_security.py`. |
| Secrets leak into the ledger/logs | Command output is **redacted** for configured secrets before it is stored as evidence. | `platforms/*/tests/test_effectors.py` (redaction). |
| Unauthorized actor runs / lands / overrides | Layered authz: **L1 tenant** (`client_id`/`project_id`/`allowed_roots`, enforced) + **L2 RBAC** (`authorize(actor, action)` over a fixed role/action matrix). `land` and operator overrides require the `operator` role. | `tests/conformance/test_authz.py` (authz decision vectors); `platforms/*/tests/test_security.py` (`authorize`); operator-authorized `land` in `platforms/*/tests/test_acceptance.py`. |
| Prompt injection via tool/model output | **Structural**, not heuristic: the engine never interprets free-form output as commands. Actions are a typed `ExecutorResult` or a pre-written script; effects are sandboxed; output is redacted. | `platforms/*/tests/test_effectors.py` (typed actions via the `ScriptedExecutor`); `platforms/*/tests/test_acceptance.py` (full run drives only typed actions). |
| Cross-tenant leakage | `isolation_scope` + touched-path containment: an execution-log event touching a path outside `allowed_roots` is a finding (`ISOLATION.EVENT_SCOPE_MISMATCH`). | `tests/conformance/test_vectors.py` replaying `framework/conformance/vectors/ledger/event_scope_mismatch.yaml`. |

## Residual / deferred risks

These are known and tracked (`TODO.md`, `plans/DECISIONS.md` D-0015); they do not
block `v1.0.0` but bound what the current release guarantees.

- **Full identity / delegation wiring (D-0015).** L0 identity (SPIFFE / OAuth2
  client-credentials) and L3/L4 (ReBAC via OpenFGA/SpiceDB, ABAC via OPA/Cedar)
  are external PDPs plugged into the same `Authorizer` interface later. v1.0.0
  ships L1 (tenant) + L2 (RBAC) only. **Over-broad A2A delegation** (capability
  scope, bounded delegation depth) is part of this deferred layer.
- **Ledger schema migration (G10).** There is no migration story yet for
  persisted, hash-chained, signed ledgers when a future `framework/VERSION`
  changes a ledger field. Until then, a breaking ledger-shape change is a major
  version bump that does not auto-migrate existing ledgers.
- **Signing-key management.** The HMAC key is injected (`Config.signing_key` /
  env) and never committed; key storage, rotation, and distribution are the
  operator's responsibility (out of framework scope).
- **Live executors are stub-tested only.** The real `ApiExecutor` (Anthropic /
  LiteLLM) and `HostRuntimeExecutor` (Claude Code) paths are integration-only;
  the security properties above are proven on the offline/scripted path.

## Verification

All proofs above run in CI:

```bash
python -m unittest discover -s tests/conformance -v
pytest platforms/hermes platforms/claude -q
```
