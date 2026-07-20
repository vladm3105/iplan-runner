# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Vendored verified-planning slimmed to CI-only assets** — the skill is global-canonical at `~/.claude/skills/verified-planning/` (founder direction 2026-07-20); the repo-local `SKILL.md` shadowed it. Kept `check_plan.py` (synced to global master) + `.github/workflows/plan-gate.yml` + the pre-commit hook entry; removed `SKILL.md`, `PLAN-TEMPLATE.snippet.md`, `install.sh`, `precommit-hook.snippet.yaml`, vendored `tests/` and the skill-dir `plan-gate.yml` copy. Aligns with PLAN-018's OSS-migration removals (`PLAN.md`/`DESIGN.md` were already gone). Historical plan citations into removed files are point-in-time records — not retargeted.
- **markdown-lint graduated to blocking (PLAN-007 W3)** — adopted the relaxed canon `.markdownlint.json` (disables MD013/MD024/MD036), cleared the residual violations, flipped `fail-on-findings: false → true`. Cleanups were targeted + meaning-preserving (a blind `markdownlint-cli2 --fix` corrupts prose by misreading literal `+` in wrapped sentences as list markers): reflowed 16 prose-`+` lines, disabled MD033 on the two `PLAN-TEMPLATE` files (their `<placeholder>` fill-in syntax is intentional), backticked the PR-template placeholders, added `text` to 22 framework pseudo-code fences (MD040), added a `## Decision log` h2 in `plans/DECISIONS.md` so the `### D-NNNN` entries no longer skip a level under the h1 title (MD001 — the `### D-` symbols are kept intact because verified-planning Claim ledgers cite them by exact string), merged a blockquote split (MD028), escaped a literal `|` in a table code span (MD056), plus `--fix` for the structural blank-line/strong-style rules. (Also repaired two `__init__.py` file-path citations that `--fix` had mangled to `**init**.py` via MD050.) Arming as a required status check is the separate founder-executed W4 step (FT-11).
- **Re-pin aidoc-flow-ci callers to @ci/v1.9.5** — version-only bump of stale `@ci/vX.Y.Z` pins to the current canon (per `sync/check-pin-currency.sh`). Topology preserved.

### Added

- **Content-check CI workflows** — `links` (blocking, offline), `markdown-lint` (report-only, `fail-on-findings: false`), and `docs-sync` (dry-run) callers of the aidoc-flow-ci reusables @ci/v1.9.5, + `.markdownlint.json`/`.github/docs-sync.json` configs. Completes the content-check surface (labeler/secret-scan already present).

### Added — canon secret-scan (gitleaks) workflow (2026-07-11)

Adopted the aidoc-flow-ci secret-scan gate (@ci/v1.9.2, gitleaks binary).

### Changed — re-pin aidoc-flow-ci callers to @ci/v1.9.1 (2026-07-11)

Bumped audit-trail + auto-merge callers to `@ci/v1.9.1` via `install.sh --repin` (also fixes stale `v1.6.0`/`v1.5.1` pins). Version-only; ai-review (→ operations@main) untouched.

### Fixed — PLAN-025 P3 (batch 3): executor wall-clock timeout (M-wall) (2026-07-09)

`max_wall_s` could never fire — `usage["wall_s"]` was compared but never written and
no executor call took a timeout, so a hung model/host-runtime call held the receiver's
`slots` semaphore permit forever (permanent `503 receiver_busy`). New
`budget.run_with_deadline(fn, max_wall_s)` (both engines, byte-identical `budget.py`)
runs the blocking call on a **daemon** worker thread and raises `DeadlineExceeded` if it
outruns the budget; the hung worker is abandoned (never blocks interpreter exit). Both
executors (hermes `ApiExecutor.complete`, claude `HostRuntimeExecutor.run_task`) now wrap
their client call with it, record `usage["wall_s"]`, and return `BUDGET.TIME_EXCEEDED` on
timeout — so the run unwinds and the slot is reclaimed. `max_wall_s is None` runs inline
(no thread), preserving today's behavior. Abandoning the thread does not kill the
underlying work (an orphaned subprocess/HTTP call keeps running) — only the slot is freed.

### Fixed — PLAN-025 P3 (batch 2): workspace + relay-DB retention (M-ws, M-relay) (2026-07-09)

Bounded retention so a long-running receiver does not fill disk / grow the relay DB
unbounded. Applied to both engines (`store.py` byte-identical; `service.py` differs
only by the engine-name token).

- **M-ws.** `provision_workspace` cloned a fresh repo per task into
  `<root>/<run_id>/<task_id>` and only removed it on a same-key re-run. `execute` now
  GCs the per-task clone in a `finally` after the run settles (computed up-front so a
  *failed* clone's partial dir is removed too) — and **never** the shared workspace
  root (the string/file-intake shape, which runs over the root, is untouched).
- **M-relay.** The relay SQLite `delivery` / `accepted_task` rows were only ever
  inserted/updated, never pruned. New `store.prune_settled(store_dir, *, max_age_s)`
  deletes settled rows older than the retention window (default 7 days): `delivered`
  `delivery` rows (a re-drain re-delivers → iplanic dedups to a harmless 202) and
  terminal (`done`/`failed`) `accepted_task` rows. Dead-lettered rows and every active
  row are **kept**; the `identity` table and on-disk ledger files are out of scope.
  Called from `execute` (receiver auto-drain, best-effort) and the CLI `sync`. The
  window (env `IOPS_RELAY_RETENTION_S`, default 7 days) must exceed iplanic's
  re-dispatch horizon — a re-dispatch of a pruned settled task would re-run (the row is
  the idempotency guard).

### Fixed — PLAN-025 P3 (batch 1): receiver body guard (M-body) + budget pre-check parity (M-budget-parity) (2026-07-09)

- **M-body.** The receiver parsed `Content-Length` with a bare `int(...)`; a
  non-numeric header raised an uncaught `ValueError` that killed the handler thread,
  and there was no body-size cap. `receiver/http.py` (both engines, byte-identical)
  now validates via `_validate_content_length` → `400 schema_invalid` on a
  malformed/negative header, `413 payload_too_large` above `_MAX_BODY_BYTES` (1 MiB).
  Covered by unit tests + a non-gated raw-socket integration test asserting the live
  server returns 400 and keeps serving.
- **M-budget-parity.** claude `HostRuntimeExecutor.execute` gained a PRE-spend budget
  `check` (mirroring hermes `ApiExecutor`), so once usage is over budget the next task
  is refused without invoking the host runtime — previously it ran one extra task.

### Security — PLAN-025 P1: clone-URL RCE (B1) + reject-envelope wire fix (B3) (2026-07-09)

Pre-prod hardening, P1 blockers from `plans/PLAN-025_preprod-hardening.md`. Applied
to **both engines** in lockstep (`platforms/claude`, `platforms/hermes`); the shared
modules stay byte-identical.

- **B1 — RCE via clone URL (fixed).** A dispatched task's
  `context_package.repository.url` reached `git clone` with only a non-empty-string
  check; `ext::sh -c <cmd>` triggered git's `ext::` remote-helper → arbitrary shell
  on the runner host (`file://`, leading-dash args, and scp-like forms were also
  accepted). Now `validation/payload_rules.py` enforces a transport allow-list at the
  door — only `https`/`ssh` with a non-empty authority; `ext::`/`file://`/`http://`/
  `git://`/scp-like/leading-dash/authority-less URLs are rejected
  (`REMOTE.PAYLOAD_REPOSITORY_URL_SCHEME`), and a leading-dash `base_ref`/
  `default_branch` (an option-injection a trailing `--` does not stop) is rejected
  (`REMOTE.PAYLOAD_REPOSITORY_REF`). `vcs/git.py` adds argv hardening (`git clone …
  -- <url> <dest>`, `git checkout <ref> --`) **and** a self-protecting sink guard in
  `clone()` that refuses the `<transport>::` remote-helper form and leading-dash URLs
  unconditionally — so no future caller (or the test-only scheme exemption) can route
  a remote-helper URL into git. Test-only env exemption `IOPS_INSECURE_CLONE_SCHEMES`
  re-permits `file://` for the gated local-clone fixtures; it is default-closed and
  can never re-enable `ext::` (the sink guard blocks it regardless).
- **B3 — reject-envelope field mismatch (fixed).** `relay/reject.py` `classify()`
  read the reject code from `reject_code`/`code`, but iplanic emits it under `reason`
  (verified against `iplanic_service/app.py`), returning `403` for `invalid_signature`
  and `400` for `timestamp_skew`. The old code dead-lettered any `403` before reading
  the code, so a forged signature was silently dead-lettered and a transient clock
  skew stalled the whole drain. `classify()` now reads `reason` (falls back to
  `reject_code`/`code`), routes the integrity + skew codes ahead of the generic `403`
  dead-letter branch, and retries all transport `5xx` before any body-code branch.
- **Conformance:** two new REMOTE-001 rule-catalog entries + vectors
  (`reject_repository_url`, `reject_repository_ref`); new unit suites
  `test_receiver_security.py` / `test_reject.py` (both engines) and a direct
  `clone()` sink-guard test. Full DB-free + gated wire suites green.

### Changed — Wave 3a adoption of aidoc-flow-ci PLAN-003 governance-file canon (2026-07-08)

iplan-runner adopts the PLAN-003 flexible-canonical (Option B) project-
governance file canon. Design in `aidoc-flow-ci#72` (plan draft);
shipment: `aidoc-flow-ci#73` (PR-V1 canon templates + Wave 0), `#74`
(PR-V2 governance-table parser), `aidoc-flow-operations#217` (PR-V3
CROSS_REPO_PLAYBOOKS §T-D + OPS-0070), `aidoc-flow-ci#75` (PR-V4 status
flip to SHIPPED + rollout playbook), `aidoc-flow-ci#76` (canon-template
polish), `aidoc-flow-ci#77` (parser §N + #anchor suffix handling),
`aidoc-flow-ci#78` (ai-review rubric repo-aware doc-coverage +
hash-count discipline), `aidoc-flow-ci#79` (canonical-source authority
disambiguation) — all merged 2026-07-08.

Governance drift check (`bash ../aidoc-flow-ci/install/apply-standards.sh
--check`) — `CLAUDE.md#per-repo-governance` now reports OK (6/6 required
rows verified + 0 additional + 0 errors).

- **`CLAUDE.md`** — `## Per-repo governance` table updated per PLAN-003
  §5.4c iplan-runner row + §4.5 parser contract:
  - Fixed `Plans` cell: was `plans/PLAN-NNN_*.md` (a naming glob that
    doesn't resolve on disk) → `plans/` (the directory).
  - Added required `Changelog | CHANGELOG.md` row (was absent per §4.5
    required-row check).
  - Cleaned annotations from `TODO / backlog` cell (was `` `TODO.md` (root) ``)
    and `Decisions log` cell (was `` `plans/DECISIONS.md` (D-0001..) ``)
    — inline parenthesized annotations still parse via §4.5 extract_path,
    but plain paths reduce clutter for a small governance table.

**Plan-baseline note (PLAN-003 §5.4c drift):** the plan anticipated
"add TODO root row + link-summary retrofit" as this repo's Wave 3
scope. In practice this repo's TODO row already existed pre-adoption,
so this PR cleans its annotation rather than adding it. Net CLAUDE.md
Δ is +1 line instead of the plan-estimated +15. Feedback to plan
author noted; no further action needed here.

- **`CHANGELOG.md`** — this entry.

**2 surfaces** (CLAUDE.md + this CHANGELOG entry). OPS-0061 Rule 1 compliant.

Deferred to follow-up PR:

- Workspace-standards blocks link-summary retrofit per PLAN-003 §5.4c
  iplan-runner row `## Workspace standards` column MODIFIED. Orthogonal
  to parser-gate concern this PR closes.

Multi-agent self-review per OPS-0065 (code-reviewer single-agent depth per minimal-scope calibration): APPROVED after 1 fold cycle addressing 1 MAJOR (TBD → filled) + 1 MINOR (plan-vs-actual drift note added — PLAN-003 §5.4c anticipated +15 lines but this repo's TODO row already existed, so net Δ is +1 line)

### Added — Wave 3 product-tier adoption of aidoc-flow-ci canon (PLAN-002 §5.5) (2026-07-08)

Self-adopts the workspace-wide standards canon from `aidoc-flow-ci@ci/v1.6.0`
per PLAN-002 §5.5 Wave 3 (product-code tier). Adds mechanical OPS-0069
audit-trail enforcement + workspace-baseline governance surfaces. 8 file
surfaces + this CHANGELOG (atomic canon-adoption bundle per PLAN-002 §5.5
explicit exemption to OPS-0061 Rule 1's ≤3-surface cap; same precedent as
PR-U4 on aidoc-flow-ci and PR #13 on iplan-standard):

- **`scripts/pre_push_check.sh`** (NEW) — canon self-review script (byte-
  identical to canon at `ci/v1.6.0`).
- **`.pre-commit-config.yaml`** (edit) — canon block MERGED into existing
  config via ruamel.yaml round-trip (preserves consumer comments + hooks);
  `# CANON: aidoc-flow-ci pre_push_check` marker at line 1 so future
  install.sh re-runs no-op.
- **`.github/pull_request_template.md`** (NEW) — canon PR template.
- **`.gitignore`** (edit) — merged canon baseline lines (13 lines appended).
- **`.gitattributes`** (NEW) — canon baseline.
- **`.github/workflows/audit-trail.yml`** (NEW) — consumer caller wiring
  `audit-trail-check.yml` reusable at `@ci/v1.6.0`. Check-name = `call / verify`.
- **`.github/workflows/standards-drift.yml`** (NEW) — weekly cron running
  `bash sync/check-standards-drift.sh --tier product` (script fetched from
  canon at runtime). Warning-only per canon §3.1b.

**Intentional canon-divergence (preserved existing consumer customization):**

- **`.github/CODEOWNERS`** — PRESERVED existing repo-specific per-path routing
  (`/framework/`, `/platforms/`, `/tests/`, etc.). More useful than the flat
  canon shape (single-owner `*` → `@vladm3105` only). Will show DRIFT vs
  `apply-standards.sh --check` — documented as intentional consumer
  customization within the spirit of `REPO_STANDARDS.md` §7.
- **`.github/dependabot.yml`** — PRESERVED existing per-platform pip paths
  (`/platforms/hermes`, `/platforms/claude`, `/tests/conformance`) which are
  more granular than the canon flat `directory: /`. Will show DRIFT — same
  rationale as CODEOWNERS.

**Server-side follow-up (F5 blast-radius; not in this PR):** founder runs
`bash install/apply-standards.sh --apply --repo vladm3105/iplan-runner
--tier product --ci-tag ci/v1.6.0 --yes` to add `call / verify` to
branch-protection contexts per `REPO_STANDARDS.md` §14.3 + apply canon
labels + repo-settings + actions-permissions + branch-protection-product.

**Origin:** `aidoc-flow-ci/plans/PLAN-002_workspace-standards-rollout.md`
§5.5 Wave 3 (product-code tier).

### Fixed — relay-store concurrent-writer "database is locked" flake (2026-07-06)

- **`relay/store._connect`** (both engines) now serializes the per-connection
  `PRAGMA journal_mode=WAL` switch + schema init behind a module lock. SQLite does
  **not** invoke the busy handler for a journal-mode change, so concurrent
  first-time WAL switches (the receiver runs parallel worker threads over one
  `relay.db`) raced to `sqlite3.OperationalError: database is locked` despite the
  5 s `busy_timeout`. Reproduced at ~7-in-150; **0/300** after the fix. Once WAL is
  set (a persistent DB property) the switch is a cheap no-op, and the actual
  read/write statements still run concurrently. Fixes the intermittent
  `test_concurrent_writers_do_not_error` CI failures.

### Added — PLAN-023: config-selected receiver executor (D-0025, 2026-07-05)

- **`Config.receiver_executor`** (`= "mock"`, from the `receiver.executor` YAML
  key) + **`cli/_server`** now builds `ReceiverDeps` **with** a `make_executor`
  factory chosen by it (the PLAN-022 seam), instead of the hard-wired default.
- **Engine-specific** (each engine ships its own real-agent executor, D-0013):
  claude `host` → `engine.host_executor(StubRuntimeClient(), ws)` (the
  `HostRuntimeExecutor` budget+scope governor); hermes `api` →
  `engine.api_executor(StubModelClient(), ws)` (the `ApiExecutor`); `mock`
  (default) → today's `MockExecutor`. Unknown mode → fail-loud boot.
- **Stub-only → fully CI-able.** `host`/`api` exercises the real governance path;
  the **real** client adapters (Claude Code hook / `get_model_client`) are a
  config-guarded PLAN-024 swap (integration-only). Budget left at `Budget()`.
- +5 tests per engine (config load, factory selection/fail-loud, `execute`
  through the real governor with the stub → `done`). Engine-specific wiring is
  legal under the version+isolation "spec parity" (not a source diff).

### Added — PLAN-022: repo → workspace clone + executor seam (D-0024, 2026-07-05)

- **`vcs/git.py: clone(url, ref, dest)`** (both engines) — a full (non-shallow)
  `git clone` + `checkout <ref>`, so a branch, tag, or arbitrary-SHA `base_ref`
  resolves. Fixed-argv / no-shell, like the landing helpers.
- **`receiver/service.provision_workspace`** — the receiver now **clones the
  dispatched repository** `{url, base_ref}` into a per-run
  `<workspace>/<run_id>/<task_id>` and runs the task against that working copy
  (isolation binds to it via `allowed_roots`). A string repository (file-intake
  shape) passes through unchanged. `_slug` sanitizes the payload-controlled
  `run_id`/`task_id` so they cannot escape the workspace root.
- **`ReceiverDeps.make_executor`** — the executor is now an injectable factory
  (default preserves today's `MockExecutor`), so a real executor drops in with
  no receiver change.
- **Clone-only slice** — the real-agent executor (`HostRuntimeExecutor` + a real
  `RuntimeClient` adapter, integration-only) is deferred to **PLAN-023**.
- Both engines byte-parallel (D-0011). +2 vcs + 7 workspace tests/engine; the
  gated wire suite now clones a local `file://` fixture. 137 offline + 6 gated
  per engine, 26 conformance, ruff + `mypy --strict` clean.

### Added — IPLAN-0030 P5 Phase B: server-side auto-merge-ai-prs enforcer caller (2026-07-05)

- **`.github/workflows/auto-merge-ai-prs.yml`** (NEW, ~65 lines) — thin
  caller for the aidoc-flow-ci reusable enforcer, pinned at `@ci/v1.5.1`.
  Triggers on `workflow_run` chain-off from `ai-review` + `composition`
  completion (per IPLAN-0030 §2.2 architecture — NOT `check_suite` per
  Pass-2 C1 anti-recursion finding) + `workflow_dispatch` for operator
  manual recovery. `if: workflow_dispatch || workflow_run.conclusion ==
  'success'` guard skips non-success fires.
- **Runner topology:** `ubuntu-latest` (reusable default) — omits
  `runner_labels` since iplan-runner uses `ubuntu-latest` across all
  existing workflows (ci.yml, plan-gate.yml, security.yml, etc.). Contrast
  with operations Phase A pilot which passes `["self-hosted","aidoc","ci-ephemeral"]`.
- **Origin:** IPLAN-0030 P5 Phase B rollout per plan §3. iplan-runner is
  1 of 6 allowlisted Phase B consumers (`vladm3105/iplan-runner` in
  `operations/.github/ai-review/config.json` `auto_merge.repos`). Phase A
  pilot (operations) merged as `84abfc2` (@ci/v1.5.1) + validated with
  10 fires + 0 false-merges.
- **Firing model:** the `workflow_run` chain-off path is dormant until
  ai-review begins firing (post-App-install per CLAUDE.md § Unified CI —
  the F5 blast-radius prerequisite). The `workflow_dispatch` path
  remains operator-invokable at any time, gated by the reusable's
  trust-gate (fail-closed) + `auto_merge.repos` allowlist (iplan-runner
  IS in the allowlist). App-installation completes the App-attributed-
  merge guarantee (pre-install merges would be `github-actions[bot]`-
  authored under GITHUB_TOKEN fallback with a `::warning::`).
- **`composition` in `workflows: [...]`:** forward-compat for the pending
  IPLAN-0017 Phase C migration when iplan-runner adopts `composition.yml`
  alongside its migrated ai-review pin. `workflow_run` silently no-ops on
  unmatched workflow names, so listing it early is harmless.
- **🟡 governance PR** (`.github/workflows/`). AI does NOT auto-merge
  per OPS-0062 §exceptions.

### Added — Inbound A2A task receiver (PLAN-021, D-0022) (2026-06-27)

- **`POST /v1/tasks` receiver** (both engines, stdlib `http.server`, opt-in
  `receiver.enabled`, gated out of CI): mandatory constant-time bearer, a bounded
  daemon-thread run pool (`503 receiver_busy` at capacity), prompt-ACK-then-background.
  iplanic can now **dispatch a task over the wire** (not just a file) and the run's
  signed events drain back through the existing relay.
- **`(run_id, task_id)` idempotency** — a new `accepted_task` table in the relay
  SQLite with split `accept_task` (durable, gates the ACK) + atomic `claim_task`
  (`accepted → running`, gates the run): two concurrent POSTs ACK but exactly one
  runs; a crash-orphaned `accepted` row re-runs; a `running`/terminal row replays.
- **`receiver/` package** (`auth`, `service`, `heartbeat`, `http`) + a `receiver`
  config block + a `server` CLI verb + a background heartbeat
  (`POST /executors/{id}/heartbeat`) that keeps the executor dispatchable.
- **Intake + validation** — `ingest_task_payload_dict` (canonical-hash checksum) +
  `adapt_dispatched_task` (nested `context_package.repository` object → workspace
  path); `validate_payload` gains `REMOTE.PAYLOAD_REPOSITORY_SHAPE` (backward
  compatible — a string repository stays valid). Inbound section added to
  `framework/remote/REMOTE_EXECUTOR_CONTRACT.md`; a `reject_repository` conformance
  vector added; the `accept` vector's manifest acceptance is now the runnable dict shape.
- **No iplanic PR remains** (dispatcher-auth shipped, iplanic PLAN-048/D-0067) — only
  the two-pairing provisioning per iplanic `docs/runbooks/EXECUTOR-DISPATCH-SETUP.md`.
- Deferred → PLAN-022: live executor, repo→workspace clone, auto re-drain,
  crash-recovery, mTLS/OIDC inbound auth.

### Added — CLAUDE.md: OPS-0062 AI agent auto-merge default rule (applies to ALL AI agents) (2026-06-27)

- **`CLAUDE.md`** new section **"AI agent auto-merge default (OPS-0062)"**
  after the existing "Governance PR discipline (mandatory)" section.
- **Canonical record:** operations `ops/DECISIONS.md` OPS-0062 (PR #152
  merged 2026-06-27 commit `dcc4692`).
- AI agents (Claude, Codex, Gemini, etc.) opening PRs in this repo default
  to auto-watch + auto-merge when green; escalate to human at 10 attempts.
- Exceptions explicitly preserve this repo's governance PR list.

### Added

- **`CLAUDE.md` — new "Governance PR discipline (mandatory)" section.** Two
  rules for any PR touching `plans/DECISIONS.md`, plan files, `CLAUDE.md`,
  `.github/ai-review/` or `.github/workflows/ai-review.yml`, or
  superseding a locked decision: (1) ≤3 doc surfaces per PR (split if
  more); (2) mandatory adversarial self-review before every push
  (dead refs / supersession completeness / internal consistency).
  Reconciliation paragraph clarifies the rule does NOT supersede the
  existing doc-currency rule — it scopes how doc-currency applies
  per-PR. Origin: operations 2026-06-23 (22+ ai-reviewer findings
  across operations PRs #107-109 in one session). Cross-references
  `aidoc-flow-operations` `CLAUDE.md` + `OPS-0061`.

### Changed

- **`CLAUDE.md` — new "Unified CI — consume from `aidoc-flow-ci`" section
  (PR #48, merged 2026-06-23 as `859ef45`).** Codifies this repo's
  consumption pattern for the planned `aidoc-flow-ci` shared CI library
  (`vladm3105/aidoc-flow-ci`, public, semver-tagged `ci/v1.0.X`) per
  the unified-CI design in `aidoc-flow-operations` IPLAN-0017 + the
  charter at `aidoc-flow-operations`
  `ops/iplans/IPLAN-0017-CHARTER_aidoc-flow-ci.md`. Documents the
  foundational "local overrides shared" rule + 3 override modes
  (parameter override / full replacement / add custom workflow) +
  warning-only drift detection. Per-repo state captured: private repo;
  ai-review.yml WIRED via PR #45 (merged 2026-06-19) but the gate is
  inert until the reviewer App is installed on this repo. Migration
  to `uses: vladm3105/aidoc-flow-ci/...@ci/v1.0.0` happens in **Phase
  C** of IPLAN-0017 rollout when the App is installed + Steps 1-3
  activation mirror are run per IPLAN-0016 §2a-v3.
- **Consume the IPLAN standard (PLAN-023 / D-0023).** iplan-runner is now a **pinned consumer** of
  [`iplan-standard@iplan/v0.1.0`](https://github.com/vladm3105/aidoc-flow-iplan-standard), replacing the
  stale hand-copied fork:
  - The `framework/remote/` task-payload mirror is **re-derived** to the current shape (the `repository`
    object, fixing the `repository: "."` drift) and all provenance is re-pinned (`fb5f46d`/`1.3-draft` →
    `iplan/v0.1.0`).
  - The standard's `iplan_canonical` is **vendored as a package** (`security/iplan_canonical/`) in each
    engine; `security/iplanic_signing.py` is now a thin re-export shim over it — same public API, so
    importers + the conformance suite are unchanged, and hashes/signatures are byte-identical to iplanic by
    construction. Runner-local `.pyi` stubs keep `mypy --strict` clean over the verbatim untyped package.
  - **`sync/check-drift.sh`** byte-diffs the vendored package (per engine) + the canonicalization vectors
    against the pinned tag and fails on drift. Conformance 26 + 244 offline tests green; ruff/mypy clean.
- **Relay operational store → SQLite (D-4c, PLAN-020 / D-0021).** The relay's
  cursor / dead-letter / persisted identity move from JSON sidecars to a per-store
  SQLite database (`<store>/relay.db`, stdlib `sqlite3` — **no new dependency**, WAL).
  It is an **outbox keyed on the stable `idempotency_key`**, so a dead-letter write
  is an atomic settle (the row *is* the cursor mark) — closing the D-4b two-write
  crash-window — and mirrors iplanic's transactional outbox for symmetric
  at-least-once reasoning. `relay/store.py`'s public interface is unchanged (worker /
  CLI / gated suite unaffected). The signed hash-chained ledger stays a portable file.
- **`execution-event` id/idempotency_key/trace_id anchored on the hash chain (D-4b).**
  Derived from the D-0008 `event_hash` (with an `event_type` discriminator for the
  `task.completed`+`test.*` fan-out that shares one `event_hash`) instead of a
  positional counter, so re-projection is byte-stable and iplanic's `idempotency_key`
  dedup holds. The wire shape is unchanged — values only; the projection golden
  `framework/conformance/remote/accept/expect.yaml` was regenerated and the
  cross-engine differential re-proven.
- **Version scheme corrected to pre-1.0.** `framework/VERSION` (the execution
  contract) `1.2.0 → 0.14.0`; registry `spec_version` and both engines'
  `FRAMEWORK_SPEC_VERSION` follow in lockstep; engine package versions
  `1.0.0 → 0.14.0`. The contract is still evolving (Phase-D work), so `0.x`
  honestly signals pre-stable — matching the framework's convention of keeping
  an evolving spec at `0.x`. `1.0.0` is reserved for GA / contract-freeze. No
  behavioral or contract change — numbering only. (Continues the pre-jump `0.x`
  line: the premature `1.0.0/1.1.0/1.2.0` map to `0.12.0/0.13.0/0.14.0`.)
- **Renamed the engine packages `iops_hermes` → `iplan_hermes` and `iops_claude` →
  `iplan_claude`** (dist names `iplan-hermes`/`iplan-claude`; CLI entry points
  `iplan-hermes`/`iplan-claude`; `framework/registry/EXECUTION_REGISTRY.yaml` package
  keys updated so the conformance loader resolves both engines). Engine identities
  `hermes`/`claude`, the contract, the vectors, and the Iplanic wire surface are
  unchanged — rename only. **Dropped the former engineering codename.** (D-0019.)

### Added

- **iplanic transport (D-4b, PLAN-019 / D-0020).** A per-engine `relay/` package
  (hermes + claude, byte-identical) that streams the local signed execution ledger
  to iplanic `POST /v1/events`, gated by a config sync toggle (**off by default**):
  - `relay/client.py` — stdlib HTTP POST with an injected bearer-token provider
    seam (D-0015 boundary), bounded transport/5xx retry+backoff, scheme-guarded to
    http(s).
  - `relay/reject.py` — the PLAN-017 reject→outcome classifier (202→advance,
    `timestamp_skew`→local far-stale heuristic, 403→dead-letter, 401→refresh-once,
    integrity/unknown→halt).
  - `relay/store.py` — durable settled-cursor keyed on the stable projected
    `idempotency_key`, dead-letter sink, and the persisted iplanic-identity sidecar.
  - `relay/worker.py` — at-least-once drain loop; the dead-letter is committed
    **before** the cursor advances (no silent loss).
  - CLI `iplan-<engine> sync` (on-demand drain, `--payload`/`--dry-run`) + an
    `iplanic` sync block on `Config` (`sync.enabled` default false, endpoint,
    `token_env`). A sync-disabled run opens no socket.
  - Gated fake-iplanic integration suite (`IPLAN_FAKE_IPLANIC=1`, not in CI).
- `security/iplanic_signing.py` (both engines): the `iplan-canonical-json` signer
  for Iplanic `execution-event` emission — RFC 8785 JCS + `sha256` + recursive
  drop-null, signed payload excluding `{signature, received_at}`, raw-byte HMAC
  key, and `ed25519` — making IOPS signatures byte-reproducible by Iplanic. The
  standalone authenticated-ledger signer is unchanged. (PLAN-014, D-0017.)
- Vendored Iplanic golden vectors (`framework/remote/iplanic-vectors/`,
  version-pinned) and a cross-engine conformance test reproducing them byte-for-byte
  (canonical bytes, `sha256`, and `hmac-sha256`/`ed25519` signature values).
- `rfc8785` and `cryptography` engine dependencies (for the Iplanic signer).
- Iplanic **remote-executor conformance** (PLAN-013, D-0016): a second intake front
  door `ingest_task_payload` maps the Iplanic task payload to the same
  `iplan-intake` manifest (run loop unchanged), and `to_execution_events` projects
  the signed ledger into Iplanic `execution-event`s (consuming the D-0017 signer).
  Both engines emit byte-identical events; conformance asserts the projection,
  required-field coverage, and the cross-engine differential.
- `REMOTE.PAYLOAD_*` payload validation (`validation/payload_rules.py`, category
  `REMOTE-001`) and the `framework/remote/` contract + vendored consumed-subset /
  emitted-required-field mirrors.
- Sandbox `classify_path` gains an optional `forbidden_paths` arg + `SANDBOX.FORBIDDEN`
  reason (checked after the positive jail; existing callers unchanged).
- CLI: `intake --payload <file>` and `emit-events <ledger> --payload <file>`.
- `REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT` payload validation (both engines): a task
  payload whose `executor_id` is present but not the Iplanic hash form
  `^exec:[a-z2-7]{16,}$` is rejected at intake, with a `reject_executor_id`
  conformance vector (PLAN-015, D-0018).
- Framework spec `1.1.0`; engines `0.12.0`.

### Changed

- Re-pinned the vendored Iplanic mirrors to `1.3-draft` / commit `fb5f46d` and
  conformed IOPS's `executor_id` to the hash form `exec:<base32(sha256(...))>`
  (Iplanic §2.1 / D-0031), regenerating the golden remote-conformance event
  signatures. The vendored canonicalization vectors are unchanged (byte-identical;
  Iplanic exempted them). Framework spec `1.1.0 → 1.2.0`; engines `0.12.0 → 0.13.0`.
  (PLAN-015, D-0018.)

## [0.12.0] - 2026-05-27

Consolidation and proof; no new contract or runtime. (Originally tagged
`1.0.0`; renumbered to `0.12.0` in the pre-1.0 correction — the execution
contract is still evolving during the `0.x` series, so `1.0.0` is reserved for
GA / contract-freeze, when it becomes stable under SemVer.)

### Added

- Worked end-to-end example (`examples/`): an approved SDD-IPLAN + action script
  (real writes + checks) + monitoring manifest, with a CLI walkthrough.
- Per-engine acceptance test (`platforms/*/tests/test_acceptance.py`) driving the
  full pipeline on the example to **committed + green + monitored + signed** on
  both engines (offline, deterministic).
- Security review (`docs/SECURITY_REVIEW.md`, per-threat mitigation + its test;
  residual risks named) + `SECURITY.md` disclosure policy.
- Getting-started guide (`docs/GETTING_STARTED.md`); README capability set +
  contract-stability statement.

### Notes

- **Out of scope** (owner-deferred, tracked in `TODO.md`): `LICENSE`,
  packaging / distribution. Residual: full auth wiring (D-0015), ledger schema
  migration (G10), live-executor integration coverage.

## [0.11.0] - 2026-05-24

### Added

- Chain orchestration runtime (`framework/execution/CHAIN_MODEL.md`): `chain_order`
  (stable topo), `run_chain` composing the single-IPLAN run loop with
  upstream-reconciled gating + a between-IPLAN control checkpoint, and an
  identity-free chain ledger (`build_chain_ledger`) + `ChainResult`.
- `iops-<engine> run-chain`; chain scenarios + cross-engine chain conformance.

## [0.10.0] - 2026-05-24

### Added

- Monitoring runtime (`framework/monitoring/MONITORING_RUNTIME.md`): SLO-breach-
  driven `evaluate_alerts` (via `alert_rules[].slo_ref`) + `build_issue` record
  (bound to `@iplan`/`@ledger`); alert conformance vectors.
- Probe HTTP server (`/healthz` `/readyz` `/startupz`); live OTel metrics/logs
  behind the `[otel]` extra (no-op default offline); engine self-telemetry
  (`emit_run_telemetry`), distinct from product monitoring.

## [0.9.0] - 2026-05-24

### Added

- Operator control (`framework/execution/CONTROL_MODEL.md`): an injected
  between-task `control` checkpoint + `ledger_control.run_state`
  (`running`/`paused`/`aborted`/`completed`).
- `resume(manifest, ledger, ...)` continues a paused or crashed run from its
  persisted ledger via idempotency (no special recovery path).
- `resolve_blocker(... decision, actor)` (`approve`/`reject`/`override`) —
  operator-authorized + recorded in the signed ledger; `override` resets the task
  to pending. `pause`/`abort`/`resume`/`resolve` CLI over the store.
- `aborted` control scenario + `run_state` in the scenario projection.

## [0.8.0] - 2026-05-24

### Added

- Config + secrets contract (`framework/config/CONFIG_CONTRACT.md`) +
  `load_config` (file + env merge; secrets/signing_key from env only).
- Resource governance (`framework/execution/RESOURCE_GOVERNANCE.md`): `Budget`
  (token/cost/wall-time) + pure `check`; `BUDGET.*` decisions + conformance.
- First **live executors** (A/B per D-0013): `hermes` `ApiExecutor` (autonomous:
  a model proposes typed actions, applied through the sandbox + budget) and
  `claude` `HostRuntimeExecutor` (governor: drive a host runtime, then govern its
  result against scope). Pluggable `ModelClient` / `RuntimeClient` with offline
  stubs; real clients import-guarded behind extras (integration-only).

## [0.7.0] - 2026-05-24

### Added

- Security model (`framework/security/SECURITY_MODEL.md`): authenticated ledger,
  layered authorization, agent-first identity (D-0015), untrusted-output
  principle, threat model.
- Authenticated ledger — `sign_ledger`/`verify_ledger` (HMAC-SHA256 over the
  canonical full event); `iops-<engine> verify --key`.
- Role-based `authorize(actor, action)` (L2 RBAC); `land(actor=...)` authorizes
  and signs when a key is configured.
- Sandbox realpath hardening (symlink-escape defense) in `apply_write`;
  `Config.signing_key` + `secrets_from_env`.
- Signing + authz golden vectors + cross-engine conformance.

## [0.6.0] - 2026-05-24

### Added

- Landing / VCS (`framework/vcs/LANDING_CONTRACT.md`): the "committed" half of
  done. VCS effector (`commit_all`/`head_sha`/`has_changes`) and a post-run
  `land()` that commits a green+reconciled run to a branch and records the commit
  in the ledger `vcs` section.
- `ledger_control.requires_landing` + `LEDGER.NOT_COMMITTED` (GATE-LEDGER-006):
  a landed ledger is complete only when committed + green.
- Handover receipt `commit` field; `iops-<engine> run --land --branch`.

## [0.5.0] - 2026-05-24

### Added

- Saga runtime: bounded retry with injected backoff, idempotency skip,
  timeout-as-failure, **compensation** that undoes partial writes, and escalation
  to a blocker (`SAGA_EXECUTION_MODEL.md` runtime state machine).
- Lease lifecycle + concurrency guard (`LEASE_MODEL.md`): `lease_state`,
  `can_acquire`, `renew`.
- `ExecutorResult.retriable`; `MockExecutor` per-task attempt sequences; injected
  `sleep`; `run(..., sleep=, max_retries=)`.
- Saga scenarios + lease decision vectors + cross-engine conformance.

## [0.4.0] - 2026-05-24

### Added

- Sandbox + evidence contracts (`framework/effectors/`).
- Pure path-jail decision `classify_path` (`SANDBOX.OK` / `OUTSIDE_ROOTS` /
  `ESCAPE`), enforced *before* effects; pinned by golden vectors + differential.
- Sandboxed effectors (`apply_write`, `run_command`), an evidence runner that
  runs acceptance checks, deterministic secret redaction, and a `ScriptedExecutor`
  that performs real effects from an action script.
- `iops-<engine> run --actions/--workspace` for real-effect runs.

## [0.3.0] - 2026-05-24

### Added

- Execution **run model** (`framework/execution/RUN_MODEL.md`) and **executor
  contract** (`framework/engines/EXECUTOR-CONTRACT.md`).
- Orchestrator + task state machine: drives an `iplan-intake` manifest through
  `pending → in_progress → completed | blocked` (dependency order, unmet-deps
  blocking), recording a hash-chained ledger.
- Pluggable `Executor` interface + deterministic `MockExecutor` (injected
  clock + id source).
- Durable, atomic, lock-guarded ledger persistence + a status/query surface.
- Gate-as-veto wired at the completion boundary; `iops-<engine> run` and
  `status` commands (CLI refactored to a `cli/` package).
- Scenario-vector conformance: per-engine projection + cross-engine differential.

## [0.2.0] - 2026-05-24

### Added

- IPLAN **intake** contract (`framework/intake/`): normalize an approved SDD
  IPLAN into a validated `iplan-intake` manifest (task graph) via a configurable
  field mapping; `INTAKE-001` rules.
- IPLAN **handover** contract (`framework/handover/`): `iplan-handover-receipt`
  published back toward the control plane; `HANDOVER-001` rules.
- Per-engine `ingest_iplan`, intake/handover validators, deterministic handover
  builder (injected clock), CLI `intake` / `handover` commands.
- Golden vectors for both new document types + a cross-engine **reader-parity**
  conformance test.

## [0.1.0]

### Added

- Planning artifacts and architecture decisions (D-0001..D-0012).
- Engine-agnostic execution contract (`framework/execution/`): ledger,
  verification-gate, chain-ledger, and audit-report templates + agent-update,
  hook-integration, saga, and isolation protocol docs.
- OpenTelemetry-aligned post-implementation monitoring contract
  (`framework/monitoring/`).
- Engine-adapter contract, execution registry, fine-grained rule-ID catalog,
  and 24 golden conformance vectors (`framework/`).
- Two fully self-contained reference engines under `platforms/`: `hermes`
  (MCP-server engine) and `claude` (Claude Code engine, AGENT_UPDATE_PROTOCOL),
  each with ledger store + hash chain, validators, gate runner, audit
  generation, OTel-optional monitoring, SLO evaluation, and a CLI.
- Conformance suite (`tests/conformance/`): vector replay, cross-engine
  differential, strict-isolation, rule-catalog coverage, and spec-version parity.
