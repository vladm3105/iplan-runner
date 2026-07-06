# PLAN-022 — Repo → workspace clone + executor seam (D-0024)

**Status:** ready-for-build (independent review PASS — 1 load-bearing fold applied, zero remaining)
**Decision:** D-0024 · **Engines:** claude + hermes (D-0011 byte-parallel) · **Date:** 2026-07-05

> **Prepared read-only** (AI authored the plan; the founder reviews + implements + owns git ops —
> cross-repo/contract-adjacent work). Scope decided with the founder 2026-07-05.

## Problem

The A2A receiver (PLAN-021 / D-0022) is a complete, authenticated, idempotent `POST /v1/tasks` front
door: it accepts a dispatched task, runs an executor, and drains the signed ledger back to iplanic's
`/v1/events`. But two things keep it from being a **live** executor:

1. **It discards the git coordinate.** `adapt_dispatched_task` rewrites the dispatched
   `context_package.repository` **object** (`{url, default_branch, base_ref}`) into a single fixed
   workspace **path string** (`intake/payload.py:124`) — its own docstring names the real repo
   clone/checkout as "a PLAN-022 concern" (`intake/payload.py:21`). So every task runs against one static
   directory, never the dispatched repo.
2. **The executor is hard-wired to `MockExecutor`.** `execute` calls
   `deps.engine.default_executor()` (`receiver/service.py:57`), which returns `MockExecutor()`
   (`engine.py:122`) — a deterministic canned executor that touches nothing real.

This slice closes **(1)** — the real, CI-able, load-bearing capability every executor needs — and makes
**(2)** a clean injection seam so a real executor drops in later **without another receiver change**. It
does **not** build the real-agent executor itself (see "Out of scope").

## Scope (minimal-and-realistic)

- **`vcs/git.py`: a `clone(url, ref, dest)` helper** — reuses the existing `_git` fixed-argv subprocess
  pattern (`vcs/git.py:9`); clones `url` into `dest` and checks out `ref`. No push/remote beyond fetch.
- **A per-run workspace provisioner** consumed in `execute` (`receiver/service.py:45`): when
  `context_package.repository` is the dispatched **object**, clone it into a per-run directory under the
  configured workspace root and hand **that path** to `adapt_dispatched_task`; when it is a **string**
  (the file-intake backward-compat shape), pass it through unchanged (no clone).
- **Executor injection seam on `ReceiverDeps`** (`receiver/service.py:33`): a factory field defaulting to
  `MockExecutor` (behaviour-preserving) that `execute` calls with the provisioned workspace, replacing the
  hard-wired `deps.engine.default_executor()` at `receiver/service.py:57`.
- **Both engines** — the identical change lands byte-parallel in `iplan_hermes` (D-0011,
  `plans/DECISIONS.md:100`).

**Out of scope (named, deferred to PLAN-023+):** the **real-agent executor** (`HostRuntimeExecutor` +
a real `RuntimeClient` adapter) — the only `RuntimeClient` today is `StubRuntimeClient` and "the real
Claude Code hook adapter is **integration-only**" (`runtime/client.py:2`), so it is un-CI-able and is the
correct follow-on, not this slice. `ScriptedExecutor` is **not** the dispatched-task executor either — it
runs a *pre-written* `actions` spec (`executor/scripted.py:31`) that a dispatched todo (description +
`acceptance_criteria` only, no actions) never carries. Also deferred: per-run workspace GC/cleanup, auto
re-drain on outage, in-flight crash-recovery, mTLS/OIDC inbound auth (the rest of the D-0022 deferred
list). No payload-template / iplanic-side change (the coordinate is already dispatched + validated).

## Design

### 1. `clone(url, ref, dest)` in `vcs/git.py`

`vcs/git.py` is landing-only today (`has_changes`/`head_sha`/`current_branch`/`commit_all`) over a shared
`_git(workspace, *args)` = `subprocess.run(["git","-C",str(workspace),*args], check=True, …)` fixed-argv
helper (`vcs/git.py:9`) — no `clone`/`fetch`/`checkout <ref>` exists. Add:

```python
def clone(url: str, ref: str, dest: str | Path) -> str:
    """Clone `url` into `dest` and check out `ref` (a branch, tag, or SHA). Returns the checked-out SHA."""
    subprocess.run(["git", "clone", "--no-single-branch", url, str(dest)], check=True, capture_output=True, text=True)
    _git(dest, "checkout", ref)          # ref may be a SHA → clone must not be shallow
    return head_sha(dest)
```

The **full clone (no `--depth`)** is what makes an arbitrary-SHA `base_ref` checkout-able — a plain
`git clone` already fetches every branch's + tag's objects, so a subsequent `git checkout <sha>` resolves
to a detached HEAD for any commit reachable from a fetched ref. `--no-single-branch` is
redundant-but-harmless here (a non-`--depth` clone is already multi-branch); it is kept only as an
explicit "not shallow" marker. **Edge (accepted):** a SHA reachable **only** from an un-fetched ref
(`refs/pull/*`, gerrit change refs, a force-pushed-away commit) fails checkout → the task settles
`ok=False` — acceptable, since a dispatched `base_ref` is always a real branch commit. Same fixed-argv /
`check=True` / no-shell posture as `_git` (the `# nosec` rationale carries). `git clone` is
`["git","clone",…]` (not `git -C`), so it is a sibling call, not a `_git` call — a small deliberate
exception to the helper.

### 2. `provision_workspace(payload, root)` — clone-or-passthrough

A pure-ish helper (new small module `receiver/workspace.py`, or a function in `receiver/service.py`) that
reads the **raw** payload's `context_package.repository` **before** `adapt_dispatched_task` overwrites it:

```python
def provision_workspace(payload, root, *, run_id, task_id):
    repo = (payload.get("context_package") or {}).get("repository")
    if isinstance(repo, dict):                       # dispatched object → clone
        dest = Path(root) / _slug(run_id) / _slug(task_id)
        clone(repo["url"], repo["base_ref"], dest)   # url/base_ref guaranteed present + non-empty (validation)
        return str(dest)
    return str(root)                                 # string repository (file-intake shape) → passthrough
```

The dispatched object's `{url, default_branch, base_ref}` fields are guaranteed non-empty strings by the
door validation (`REMOTE.PAYLOAD_REPOSITORY_SHAPE`, `validation/payload_rules.py:54` over
`_REPOSITORY_FIELDS`, `validation/payload_rules.py:22`) — so `provision_workspace` may read them without
re-validating. `base_ref` is the checkout target (`default_branch` is the repo's default, unused for
checkout in this slice). The per-run dest is keyed by `(run_id, task_id)` (the receiver's idempotency
identity) so a re-dispatch clones a fresh workspace deterministically.

**`_slug` MUST be path-safe (load-bearing).** `run_id`/`task_id` are validated only as **non-empty**
strings (`_REQUIRED_IDS`, `validation/payload_rules.py:14`) — **no charset constraint** (unlike
`executor_id`'s regex). Since the dest is `Path(root)/_slug(run_id)/_slug(task_id)`, a crafted
`task_id` like `../../etc` would otherwise escape the workspace root (a path traversal, even under
bearer auth — the id is payload-controlled). `_slug` therefore MUST neutralize path separators and
parent refs: reject or replace any `/`, `\`, `.` -run (`..`), and non-`[A-Za-z0-9._-]` char (e.g.
`re.sub(r"[^A-Za-z0-9._-]", "_", s)` then reject a `_slug` that is empty, `.`, or `..`). A component
that sanitizes to empty/`.`/`..` fails the task (`settle_task(ok=False)`), never a silent fallback.

### 3. `execute` wiring (`receiver/service.py`)

Today (`receiver/service.py:55-57`):

```python
adapted = adapt_dispatched_task(payload, workspace=deps.workspace)
manifest = ingest_task_payload_dict(adapted)
run_result = deps.engine.run(manifest, deps.engine.default_executor(), clock=_default_clock, ids=IdSource())
```

becomes:

```python
workspace = provision_workspace(payload, deps.workspace, run_id=run_id, task_id=task_id)  # clone or passthrough
adapted = adapt_dispatched_task(payload, workspace=workspace)                             # overwrites repository → this path
manifest = ingest_task_payload_dict(adapted)
run_result = deps.engine.run(manifest, deps.make_executor(deps.engine, workspace), clock=_default_clock, ids=IdSource())
```

`adapt_dispatched_task` still overwrites `context["repository"] = str(workspace)` (`intake/payload.py:124`)
— now with the **cloned** path, so the manifest's `isolation_scope.allowed_roots = [context["repository"]]`
(`intake/payload.py:73`) binds isolation to the real materialized workspace. The clone slots **between**
`claim_task` and `adapt` (`receiver/service.py:50-55`); a clone failure is caught by the existing
`except Exception` that records `settle_task(ok=False)` + logs (`receiver/service.py:76-78`) — a bad repo
coordinate fails the task, never crashes the worker thread.

### 4. Executor injection seam (`ReceiverDeps`)

`ReceiverDeps` (`receiver/service.py:33`) gains one field (backward-compatible default):

```python
make_executor: Callable[[ClaudeEngine, str], Executor] = lambda engine, _ws: engine.default_executor()
```

The default preserves today's behaviour exactly (`MockExecutor`, ignoring the workspace) — and, being a
defaulted field placed after the existing defaulted tail (`key_id`, `log`), it is a valid dataclass
addition. **Implementation note:** `receiver/service.py` does not currently import `Executor`; the new
annotation needs `from ..executor.base import Executor` (`Callable` + `field` are already imported). The
engine already exposes `scripted_executor(spec, workspace)` (`engine.py:111`) and `host_executor(client,
workspace, budget)` (`engine.py:114`), so a future real-executor wiring is a one-line factory
(`lambda engine, ws: engine.host_executor(real_client, ws)`) with **no** further `execute` change. The
CLI `_server` builds `ReceiverDeps` (`cli/commands.py:201`) with the default (no CLI surface added this
slice).

**hermes asymmetry (for PLAN-023, not this slice):** the claude engine has `host_executor` +
`runtime/client.py`, but `iplan_hermes` has **neither** today — so the "one-line `host_executor` wiring"
above is claude-only. This slice is unaffected (the default is `MockExecutor` in both engines), but
PLAN-023 must build the hermes runtime adapter first and is therefore **not** byte-parallel.

### 5. Both engines

`iplan_hermes` mirrors `iplan_claude` byte-for-byte under strict isolation (D-0011,
`plans/DECISIONS.md:100`): the same `vcs/git.py clone`, `provision_workspace`, `execute` edit, and
`ReceiverDeps` field land in `platforms/hermes/src/iplan_hermes/…`. No shared module (isolation forbids
it); the two copies stay identical.

## Verification (all CI-able, no network)

- **`clone(url, ref, dest)`** — `git init` a fixture repo in a `tmp_path` with two commits on `main` +
  a second branch/tag; `clone("file://<fixture>", ref, dest)` for `ref` = a branch, a tag, and a SHA;
  assert the dest is checked out at the expected SHA (`head_sha`). No network (local `file://`).
- **`provision_workspace`** — a dict `repository` → clones + returns the per-run path (dest exists, at
  `base_ref`); a string `repository` → returned unchanged, no clone (backward compat); the per-run path
  is keyed by `(run_id, task_id)`.
- **`_slug` path-safety** — a `task_id`/`run_id` containing `../`, `/`, `\`, or non-`[A-Za-z0-9._-]`
  chars sanitizes so the clone dest stays under the workspace root (assert the resolved dest is a
  subpath of root); an id sanitizing to empty/`.`/`..` fails the task, never escapes.
- **`execute` end-to-end (receiver)** — a payload carrying a `file://` fixture repo object; a **spy**
  `make_executor` asserting it receives the **cloned** workspace path (not the static root); assert the
  run drains (the existing Mock path) + `settle_task(ok=True)`; a bad `repository.url` → `settle_task(
  ok=False)` + no crash (the `except` path).
- **Backward-compat** — the existing receiver suite (string-workspace / file-intake) stays green through
  the passthrough branch + the default `make_executor`.
- **hermes parity** — the same suite in `platforms/hermes/…`.

## Risks

| # | Risk | Mitigation |
| --- | --- | --- |
| 1 | A shallow clone can't check out an arbitrary SHA `base_ref` | `--no-single-branch` full clone (§1); SHA checkout tested |
| 2 | Per-run workspaces accumulate on disk (no GC) | Disclosed out-of-scope; keyed by `(run_id,task_id)` so re-dispatch is deterministic, not unbounded per task; cleanup a named follow-on |
| 3 | `clone` shells out to `git` — arg injection | Fixed-argv list-form, `check=True`, no shell (mirrors `_git`, `vcs/git.py:10`); `url`/`ref` are validation-checked non-empty strings |
| 4 | The seam invites wiring the un-CI-able real executor now | Default stays `MockExecutor`; the real `RuntimeClient` adapter is explicitly PLAN-023 (`runtime/client.py:2` integration-only) |
| 5 | Path traversal — `run_id`/`task_id` are payload-controlled + only non-empty-validated; the clone dest embeds them | `_slug` neutralizes `/`,`\`,`..`/non-`[A-Za-z0-9._-]` (§2); a component sanitizing to empty/`.`/`..` fails the task; tested with a `../` id |

## Proposed decision — D-0024

Adopt repo→workspace clone + an executor-injection seam in the A2A receiver, both engines. The receiver
clones the dispatched `repository.{url,base_ref}` into a per-run workspace and binds isolation +
(future) execution to it; the executor becomes a `ReceiverDeps` factory (default `MockExecutor`). The
**real-agent executor** (`HostRuntimeExecutor` + a real `RuntimeClient` adapter) is deferred to PLAN-023
because its adapter is integration-only / un-CI-able — the same value-scrutiny that deferred iplanic's
external anchoring: build the real CI-able seam now, defer the un-CI-able external dependency.

## Claim ledger

| # | Claim | Symbol | Citation |
| --- | ----- | ------ | -------- |
| 1 | `adapt_dispatched_task` overwrites `context["repository"]` with the workspace path string — dropping the dispatched `{url,default_branch,base_ref}` object | `context["repository"] = str(workspace)` | platforms/claude/src/iplan_claude/intake/payload.py:124 |
| 2 | The adapter's own docstring names the repo→workspace clone as the PLAN-022 concern | `PLAN-022` | platforms/claude/src/iplan_claude/intake/payload.py:21 |
| 3 | `execute` runs the executor from the injectable seam — `deps.engine.run(manifest, deps.make_executor(deps.engine, workspace), …)` (the swap point; pre-impl this was the hard-wired `deps.engine.default_executor()`) | `deps.make_executor(deps.engine, workspace)` | platforms/claude/src/iplan_claude/receiver/service.py:100 |
| 4 | `default_executor()` returns `MockExecutor()` — the hard-wired canned executor the seam replaces | `def default_executor` | platforms/claude/src/iplan_claude/engine.py:122 |
| 5 | `execute` flow claim → adapt → ingest → run → save → drain → settle; the clone slots between claim (`:50`) and adapt (`:55`) | `def execute` | platforms/claude/src/iplan_claude/receiver/service.py:86 |
| 6 | `ReceiverDeps` (dataclass) — where the `make_executor` factory field is added | `class ReceiverDeps` | platforms/claude/src/iplan_claude/receiver/service.py:68 |
| 7 | `ReceiverDeps.workspace` is a single string wired once — reinterpreted as the clone root | `workspace: str` | platforms/claude/src/iplan_claude/receiver/service.py:73 |
| 8 | A clone/run failure is caught by the existing `except Exception` → `settle_task(ok=False)` + log (worker never crashes) | `store.settle_task(deps.store_dir, run_id, task_id, ok=False)` | platforms/claude/src/iplan_claude/receiver/service.py:121 |
| 9 | `vcs/git.py` is landing-only over the `_git(workspace,*args)` fixed-argv helper — no clone/fetch/checkout exists | `def _git` | platforms/claude/src/iplan_claude/vcs/git.py:9 |
| 10 | `_git` = `subprocess.run(["git","-C",str(workspace),*args], check=True, …)` — the fixed-argv/no-shell pattern the `clone` helper mirrors | `subprocess.run` | platforms/claude/src/iplan_claude/vcs/git.py:10 |
| 11 | After adapt, the manifest's `allowed_roots` = `[context["repository"]]` → isolation binds to the cloned path | `allowed_roots` | platforms/claude/src/iplan_claude/intake/payload.py:73 |
| 12 | The dispatched `repository` object's required fields `{url, default_branch, base_ref}` | `_REPOSITORY_FIELDS` | platforms/claude/src/iplan_claude/validation/payload_rules.py:22 |
| 13 | `REMOTE.PAYLOAD_REPOSITORY_SHAPE` validates the object at the door (all three non-empty strings) → clone may trust the shape | `REMOTE.PAYLOAD_REPOSITORY_SHAPE` | platforms/claude/src/iplan_claude/validation/payload_rules.py:54 |
| 14 | `engine.host_executor(client, workspace, budget)` factory already exists — a future real-executor wiring is one line | `def host_executor` | platforms/claude/src/iplan_claude/engine.py:114 |
| 15 | `engine.scripted_executor(spec, workspace)` factory (the executor is already workspace-parameterizable) | `def scripted_executor` | platforms/claude/src/iplan_claude/engine.py:111 |
| 16 | `ScriptedExecutor` runs a pre-written `actions` spec — so it is NOT the dispatched-task executor (a dispatched todo carries no actions) | `task_spec.get("actions"` | platforms/claude/src/iplan_claude/executor/scripted.py:31 |
| 17 | The real-agent path (`HostRuntimeExecutor` via `RuntimeClient`) is deferred: the real Claude Code hook adapter is integration-only / un-CI-able | `integration-only` | platforms/claude/src/iplan_claude/runtime/client.py:2 |
| 18 | `Config.receiver_workspace = "."` — the static workspace reinterpreted as the per-run clone root | `receiver_workspace` | platforms/claude/src/iplan_claude/config.py:46 |
| 19 | The CLI `_server` builds `ReceiverDeps(...)` — where the default `make_executor` + clone root thread in (no new CLI surface) | `deps = ReceiverDeps(` | platforms/claude/src/iplan_claude/cli/commands.py:201 |
| 20 | D-0011 strict engine isolation — the identical change lands byte-parallel in `iplan_hermes`, no shared module | `### D-0011` | plans/DECISIONS.md:100 |

## Review log

### Pass 1 - 2026-07-05 - author self-review

- **Clone-only + seam is the deliberately minimal slice.** The repo→workspace clone is the real,
  load-bearing, CI-able capability; the executor swap is reduced to a default-preserving injection point
  so PLAN-023 can land the real (un-CI-able) agent adapter with no receiver change. Flagged for the
  reviewer to confirm the default `make_executor` is byte-for-byte today's behaviour.
- **`ScriptedExecutor` is explicitly NOT the dispatched-task executor** — it needs a pre-written `actions`
  spec (`scripted.py:31`) a dispatched todo never carries. Recorded so the reviewer doesn't "helpfully"
  wire it. The value-scrutiny call (defer the un-CI-able real executor) mirrors iplanic's external-
  anchoring deferral.
- **`base_ref` may be a SHA → the clone must not be shallow.** `--no-single-branch` full clone; confirm
  the SHA-checkout test. Flag if a shallow+fetch-by-SHA is preferred for large repos (a later refinement).
- **Isolation binds to the cloned path** via the unchanged `allowed_roots` derivation (`payload.py:73`)
  once adapt overwrites `repository` with the cloned workspace. Confirm no other consumer of
  `context.repository` assumes the static root.
- **Both engines** land identically (D-0011); the ledger cites the claude copy — hermes mirrors.

### Pass 2 - 2026-07-05 - independent (fresh-context `code-reviewer` agent)

**20/20 ledger claims TRUE (no line drift); design verified sound.** The reviewer confirmed end to end:
the clone genuinely slots pre-`adapt` on the **un-mutated** payload (`adapt_dispatched_task` returns a
shallow copy, `payload.py:122`, so provisioning reads `context_package.repository` as the object before
it is stringified); a clone failure raises `CalledProcessError ⊂ Exception` → caught at
`receiver/service.py:76` → `settle_task(ok=False)`, worker never crashes; the default `make_executor`
lambda is byte-for-byte today's `MockExecutor` path and a valid defaulted dataclass field after the
existing defaulted tail; `engine.run` takes the executor positionally as designed; isolation rebinds to
the cloned path via the unchanged `allowed_roots` derivation (`payload.py:73`); and the four in-scope
edits are byte-parallel across claude/hermes.

**One LOAD-BEARING finding, folded:** the clone dest `Path(root)/_slug(run_id)/_slug(task_id)` embeds
**payload-controlled** ids that are validated only non-empty (`_REQUIRED_IDS`,
`validation/payload_rules.py:14`, no charset) — a crafted `task_id` (`../../…`) would escape the
workspace root (path traversal). **Folded:** Design §2 now specifies `_slug` neutralizes
`/`/`\`/`..`/non-`[A-Za-z0-9._-]` and fails a component that sanitizes to empty/`.`/`..`; a Risk row + a
path-safety test were added. **Minors, folded:** (a) `receiver/service.py` must add
`from ..executor.base import Executor` for the new annotation; (b) the `--no-single-branch` rationale
corrected (non-shallowness comes from omitting `--depth`; the flag is redundant-but-harmless) + the
un-fetched-SHA edge noted; (c) the **hermes `host_executor`/`runtime/client.py` absence** noted so
PLAN-023 is not mis-scoped as byte-parallel.

**Result:** ready — the one load-bearing finding is folded; no further load-bearing findings.
