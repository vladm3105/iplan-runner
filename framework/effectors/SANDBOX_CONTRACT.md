# Sandbox Contract

Every real effect (file write, command target) is gated by a **path jail** before
it happens — the preventive counterpart to Phase 1's post-hoc
`ISOLATION.PATH_OUTSIDE_ROOTS` ledger check. The decision is a **pure** function,
so it is the parity surface (golden vectors + cross-engine differential, D-0012).

## Decision

```
classify_path(path: str, allowed_roots: list[str]) -> {allowed: bool, reason: str}
```

Algorithm (lexical; POSIX):

1. If `path` is absolute → deny, reason `SANDBOX.ESCAPE`.
2. Let `p = normpath(path)`. If `p == ".."` or `p` starts with `"../"` → deny,
   reason `SANDBOX.ESCAPE`.
3. For each root `R`, let `r = normpath(R)`. If `p == r` or `p` starts with
   `r + "/"` → allow, reason `SANDBOX.OK`.
4. Otherwise → deny, reason `SANDBOX.OUTSIDE_ROOTS`.

## Reason codes

| Code | Meaning |
|------|---------|
| `SANDBOX.OK` | Path is within an allowed root; the effect may proceed. |
| `SANDBOX.OUTSIDE_ROOTS` | Relative, non-escaping, but not under any allowed root. |
| `SANDBOX.ESCAPE` | Absolute path, or escapes the workspace via `..`. |

These are **decision outputs**, not document-validation findings — they are not
in `framework/conformance/rule-ids.yaml` (which is for `validate()` findings).

## Enforcement

`apply_write` and `run_command` call `classify_path` on every target path and
**raise before any effect** on a non-`OK` decision. A `ScriptedExecutor` action
that hits a denied path yields `outcome: failure`, so the orchestrator blocks the
task and the edit never happens.

## Out of scope (Phase 7)

Lexical normalization does **not** resolve symlinks. Real symlink/`realpath`
containment against the workspace root, resource limits, and command
allow-listing are deferred to the security phase. `apply_write` additionally
rejects at write time as defense in depth.
