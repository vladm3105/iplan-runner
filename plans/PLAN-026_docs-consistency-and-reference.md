# PLAN-026 — Docs Consistency & Reference Completion

**Goal:** Fix every verified documentation discrepancy found in the 2026-07-19
three-lens review (accuracy / cross-doc consistency / coverage) and close the
HIGH-severity reference gaps (CLI, config, env vars, receiver ops).

**Architecture:** Documentation-only plus a version-metadata alignment; no
behavioral change to `framework/` contract semantics or engine runtime. The one
`framework/` text change (REMOTE_EXECUTOR_CONTRACT response rows) documents
already-shipped behavior.

**Tech Stack:** Markdown; `check_plan.py` gate; markdownlint (blocking since
PLAN-007 W3); docs-gate CI (`CHANGELOG.md` required on `framework/`/`src` PRs).

---

| Field      | Value |
|------------|-------|
| Task       | PLAN-026 |
| Depends on | PLAN-025 (its landed fixes are what TODO.md must reflect) |
| Status     | APPROVED - 2026-07-19 |
| Feeds      | GA docs readiness (PLAN-012 scope); onboarding of external OSS users |

## Objective

A 2026-07-19 multi-agent review (3 independent lenses: docs-vs-code accuracy,
cross-doc consistency, coverage-vs-best-practice) found ~25 verified
discrepancies and 5 HIGH coverage gaps. Clusters:

1. **Stale governance surfaces** — `TODO.md` shows six shipped PLAN-025 fixes
   as open; `plans/HANDOFF.md` is three plans behind and contradicts the
   OPS-0062 merge policy; PLAN-024/025 status headers predate their own review
   logs; a stray root `HANDOFF.md` shadows the canonical one.
2. **Frozen ROADMAP** — header still says `v0.1.0`, "no CI", dead working
   branch; phases 2–10 "planned" though shipped.
3. **False doc claims** — `docs/IPLAN-ECOSYSTEM.md` calls PLAN-013
   "unimplemented" (it is DONE) and claims identical cross-repo mirrors (they
   diverged); `docs/SECURITY_REVIEW.md` reviews a "v1.0.0" that was renumbered
   to `0.14.0`; README implies all engines take three `receiver.executor`
   modes (each takes two).
4. **Reference gaps** — 11 of 17 CLI verbs (15 `add_parser` calls + the
   `pause`/`abort` loop), the whole `receiver.*`/`iplanic.*` config surface,
   all `IOPS_*` env vars, and exit codes are documented nowhere;
   `framework/config/CONFIG_CONTRACT.md` documents keys `load_config`
   silently ignores.
5. **Version-metadata drift** — engine `VERSION`/`__version__` say `0.13.0`
   while `pyproject.toml` says `0.14.0`.

## Scope

**In:**

1. Truth-sync of governance surfaces (W1) and ROADMAP (W2).
2. Accuracy fixes in README, CLAUDE.md, `docs/**` (W3, W4).
3. Engine version-metadata alignment + CHANGELOG path fix (W5).
4. New reference docs: CLI (incl. exit codes), truthful config contract with
   env-var table, receiver/sync operator how-to + example config, docs index,
   REMOTE_EXECUTOR_CONTRACT response-row completion (W6).

**Out (items 1–4 deferred to TODO "Docs backlog"; item 5 is a won't-do —
surplus scope per the size-to-problem rule):**

1. Generated Python API reference (mkdocs/sphinx).
2. Troubleshooting/FAQ page; OTel runtime-provider deep doc.
3. Release-process doc; platform-README dedup.
4. Any propagation of the resolved D-0020 ecosystem text from the iplanic
   mirror (gated on explicit approval per that mirror's own propagation note;
   W4 only removes *false* runner-local claims and marks the divergence).
5. CHANGELOG release-header restructuring for the renumbered `0.13.0/0.14.0`
   cuts — the renumbering prose (CHANGELOG.md:377) already records the
   mapping; rewriting history headers risks more confusion than it removes.

## Approach

Fix in dependency order: governance truth first (W1 — it's what reviewers and
sessions read), then the narrative docs (W2–W4), then metadata (W5), then the
new reference docs (W6) which link *from* the corrected narrative docs.

**PR slicing (governance Rule 1, ≤3 doc surfaces on governance PRs):**

| PR | Contents | Surfaces |
|----|----------|----------|
| PR-A (this plan) | `plans/PLAN-026_*.md` + `TODO.md` (tracking section **and** the PLAN-025 checkbox truth-sync — a factual tracking correction, bundled so no ledger row cites text PR-A itself deletes) | 2 |
| PR-1 (W1a) | PLAN-024 + PLAN-025 status headers + PLAN-024 `plans/HANDOFF.md:134` repoint. Rows 16/17/52/53 survive on duplicate symbols (PLAN-024:116/:12, PLAN-025:123, PLAN-018:514) — **PLAN-018 needs no citation edits; do not rewrite both of its `:96` rows** | 2 plan files (governance) |
| PR-2 (W1b) | `plans/HANDOFF.md` rewrite, delete root `HANDOFF.md`, re-ground PLAN-026 rows 13–15/18 | 3 (governance) |
| PR-3 (W2) | `ROADMAP.md` + re-ground PLAN-026 rows 6–10 | 2 (governance) |
| PR-4 (W3) | `README.md` + `CLAUDE.md` + re-ground PLAN-026 rows 11–12/30/34 (the `docs/` repo-map row is fixed here, not PR-9) | 3 (governance) |
| PR-5a (W4) | `docs/SECURITY_REVIEW.md` + `docs/GETTING_STARTED.md` + re-ground PLAN-026 rows 19/32–33 | 3 (governance) |
| PR-5b (W4) | `docs/IPLAN-ECOSYSTEM.md` + re-ground PLAN-026 rows 24–25/27 | 2 (governance) |
| PR-6 (W5) | engine `VERSION`/`__init__.py` ×2 + `CHANGELOG.md` + re-ground PLAN-026 row 21 | code + 2 doc surfaces (governance) |
| PR-7 (W6a) | `docs/CLI.md` (new) + `framework/config/CONFIG_CONTRACT.md` rewrite + `CHANGELOG.md` — the moved `budget`/`telemetry.otlp_endpoint` literals stay in the new "Reserved" section, so rows 37–38 survive; no PLAN-026 edit | 3 |
| PR-8 (W6b) | `docs/OPERATIONS.md` (new: receiver + sync how-to, example config) + `framework/remote/REMOTE_EXECUTOR_CONTRACT.md` rows + `CHANGELOG.md` — row 43's `503 receiver_busy` line is kept; no PLAN-026 edit | 3 |
| PR-9 (W6c) | `docs/README.md` index (new) + `framework/README.md` table (row 47's `conformance/vectors/` line kept) + `README.md` index link + `CHANGELOG.md` (docs-gate fires on any `framework/` touch — `tests/chg/docs_gate.py:32`); no PLAN-026 edit | 4 (non-governance) |
| PR-10 (final) | PLAN-026 Status → DONE + `TODO.md` close-out | 2 (governance) |

**Citation-shift guard (the known CI gotcha):**

- PLAN-024 cites `plans/HANDOFF.md:134` (`plans/PLAN-024_real-executor-client.md:102`);
  PLAN-018 rows 10–12 cite `docs/IPLAN-ECOSYSTEM.md:15` and
  `plans/HANDOFF.md:96` with symbol `aidoc-flow-iplanic`
  (`plans/PLAN-018_oss-public-migration.md:513-514`). PR-1 repoints
  PLAN-024's row (the reservation fact also lives in `TODO.md`'s collision
  note) **before** PR-2/PR-5 touch the cited files. PLAN-018 needs **no**
  citation edits: its rows survive on the retained `aidoc-flow-iplanic`
  literal plus the duplicate at PLAN-018:514 (the gate is symbol-
  authoritative; line drift is warning-only).
- The PR-2 HANDOFF rewrite and the PR-5 ECOSYSTEM edit MUST retain the
  literal string `aidoc-flow-iplanic` (symbol survival is what passes the
  gate; line drift is warning-only). PR-2 edits no *other* plan files
  (PLAN-018/PLAN-024) — its only plan-file edit is the PLAN-026 rows
  13–15/18 re-ground — keeping Rule 1 intact.
- After each PR, gate the non-grandfathered plans only (PLAN-013+):
  `check_plan.py` itself has no grandfathering of PLAN-001..012 — that
  filter exists in CI (`.github/workflows/plan-gate.yml:24`) and in the
  pre-commit hook config (`.pre-commit-config.yaml:64`), and running the
  script over `PLAN-0*.md` directly fails on main today.

**PLAN-026 self-ledger strategy:** the ledger below snapshots the defective
pre-fix text on `main@959287b`, so fixes delete cited symbols by design —
and symbol deletion is a hard `check_plan.py` error. Two CI gates would
catch it: plan-gate (changed plan files) and, decisively, the pre-commit job
(`.github/workflows/pre-commit.yml:31` runs `pre-commit run --all-files` on
every push/PR; the `check-plan` hook at `.pre-commit-config.yaml:58` feeds it
**every** non-grandfathered plan — PLAN-026 included once PR-A merges).
Therefore **every PR that deletes a cited symbol re-grounds the affected
PLAN-026 rows in the same PR** (mechanical citation-sync: repoint the row to
the `CHANGELOG.md` `[Unreleased]` entry or surviving text that now evidences
the fixed state). The PR table above names the rows per PR and counts
PLAN-026 as a governance surface wherever it is edited; PR-7/8/9 are
designed for symbol survival so they need no PLAN-026 edit. Every PR must
leave `pre-commit run --all-files` green at its head.

**IPLAN-ECOSYSTEM handling (W4):** the iplanic mirror resolved the "open
question" as D-0020 and states it propagates only on explicit approval. So W4
does NOT import that section. It (a) corrects the two false runner-local
claims (PLAN-013 status, "handoffs are not wired" — contradicted by the
shipped `intake --payload` / `emit-events` / `sync` / `server` surface),
(b) replaces the "identical copy" claim with a divergence note pointing at the
iplanic mirror as ahead (D-0020), (c) leaves the comparative tables alone.

**CONFIG_CONTRACT rewrite (W6a):** document the real `Config` dataclass
surface — intake-mapping keys, `iplanic.{sync.enabled,endpoint,token_env,max_age_s}`,
the 11 `receiver.*` keys with per-engine `executor` values, and the
unknown-keys-are-dropped loading behavior; move the unshipped keys (`budget`,
`telemetry.otlp_endpoint`, per-engine executor keys) to an explicit
"Reserved — not yet read by `load_config`" section rather than deleting them.
Add the env-var table here (single normative home): `IOPS_SIGNING_KEY`,
`IOPS_SECRET_*`, `IOPS_IPLANIC_TOKEN`, `IOPS_RECEIVER_TOKEN`,
`IOPS_RELAY_RETENTION_S`, `IOPS_INSECURE_CLONE_SCHEMES` (flagged
security-sensitive/test-only).

## File Structure

| Path | Responsibility |
|------|----------------|
| `TODO.md` | checkbox truth-sync + PLAN-026 tracking + docs backlog |
| `plans/HANDOFF.md` | rewritten current-state handoff |
| `HANDOFF.md` (root) | **deleted** (CI-test residue) |
| `plans/PLAN-024_*.md`, `plans/PLAN-025_*.md` | status headers → DONE-to-date reality |
| `plans/PLAN-026_*.md` (this file) | per-PR ledger row re-grounds (PR-2/3/4/5a/5b/6) + PR-10 close-out |
| `ROADMAP.md` | header/phase/pointer refresh |
| `README.md`, `CLAUDE.md` | accuracy fixes (W3) + new doc links (W6c) |
| `docs/SECURITY_REVIEW.md`, `docs/IPLAN-ECOSYSTEM.md`, `docs/GETTING_STARTED.md` | accuracy fixes |
| `platforms/{hermes,claude}/VERSION`, `src/*/__init__.py` | `0.13.0` → `0.14.0` |
| `docs/CLI.md`, `docs/OPERATIONS.md`, `docs/README.md` | new reference/how-to/index |
| `framework/config/CONFIG_CONTRACT.md` | truthful rewrite + env-var table |
| `framework/remote/REMOTE_EXECUTOR_CONTRACT.md` | add `413`/`404` response rows |
| `framework/README.md` | complete the contents table (7 missing dirs) |
| `CHANGELOG.md` | `[Unreleased]` entries per PR; fix `:12` dead script path |

## Step Sequence

### Task W1: Governance-surface truth sync (PR-1 then PR-2)

**Files:** Modify `plans/PLAN-024_real-executor-client.md`,
`plans/PLAN-025_preprod-hardening.md`, `plans/HANDOFF.md`, `TODO.md`;
Delete `HANDOFF.md` (root).

- [ ] **Step 1 (PR-1):** PLAN-025 status → records 4 passes / gate green /
  P1 + P3 **5/7** landed (PRs #71–#74; M-crash + M-rotation open),
  **P2/P4/P5/P6 open** (P5's stale-HANDOFF item
  is executed by this plan's PR-2 — say so there); PLAN-024 status →
  reviewed (Pass 2 independent), build not started; repoint PLAN-024's
  `plans/HANDOFF.md:134` citation (`plans/PLAN-024_real-executor-client.md:102`);
  PLAN-018 is untouched (symbol survival — see the Approach guard). Gate
  PLAN-013+ after the edit.
- [ ] **Step 2 (PR-2):** rewrite `plans/HANDOFF.md` (stamp 2026-07-19; PLAN-025
  state; next plan = PLAN-027, next decision = D-0026; drop the "Never
  merge" line in favor of a pointer to CLAUDE.md OPS-0062 with its
  governance-tier exception; **retain the literal `aidoc-flow-iplanic`**);
  delete root `HANDOFF.md`; re-ground PLAN-026 rows 13–15/18. (The TODO
  checkbox sync — `[x]` on B1/B3/M-body/M-budget-parity/M-ws/M-relay/M-wall
  with PR numbers; M-crash + M-rotation stay open, not in CHANGELOG — is
  done in PR-A with the tracking section.)
- [ ] **Step 3: Commit** per PR (`docs(plans): …` / `docs(handoff): …`).

### Task W2: ROADMAP refresh (PR-3)

- [ ] **Step 1:** Header → `v0.14.0` state, drop the dead working-branch row;
  phases **2–10** statuses → done-with-version (11–12 already read done);
  delete "repo currently has no CI" and G13 "not yet added"; closing
  pointers → D-0025 / PLAN-025.
- [ ] **Step 2: Commit** `docs(roadmap): sync to v0.14.0 reality`.

### Task W3: README + CLAUDE.md accuracy (PR-4)

- [ ] **Step 1:** README — `receiver.executor` line gains the per-engine
  matrix (claude: `mock|host`; hermes: `mock|api`); `iplanic.sync` →
  `iplanic.sync.enabled`; `docs/` repo-map row lists all three (soon five)
  docs.
- [ ] **Step 2:** CLAUDE.md — rewrite "Unified CI" per-repo state (public
  repo; canon consumed at `@ci/v1.9.5` across ai-review/links/composition/…;
  drop the 2026-06-22 pre-migration block).
- [ ] **Step 3: Commit** `docs: README executor matrix + CLAUDE.md CI state`.

### Task W4: docs/ accuracy (PR-5a, PR-5b)

- [ ] **Step 1 (PR-5a):** SECURITY_REVIEW — re-version to the shipped
  `0.14.0` contract: title (`:1`) plus the two body occurrences (`:26`,
  `:30-31`) — content is otherwise verified accurate;
  GETTING_STARTED — make the snippet self-contained (define `workspace`,
  show a `clock` callable), and replace `engine._config.signing_key` with
  the public config path (`load_config` / `Config.signing_key` via env);
  re-ground PLAN-026 rows 19/32–33.
- [ ] **Step 2 (PR-5b):** IPLAN-ECOSYSTEM — per the Approach: fix PLAN-013
  status + "not wired" claim; replace "identical copy" with the divergence
  note; retain the `aidoc-flow-iplanic` literal; re-ground PLAN-026 rows
  24–25/27.
- [ ] **Step 3: Commit** per PR (`docs: fix stale version/status claims`).

### Task W5: Version metadata + CHANGELOG path (PR-6)

- [ ] **Step 1:** `platforms/{hermes,claude}/VERSION` and both
  `__init__.__version__` → `0.14.0` (aligning with `pyproject.toml`);
  CHANGELOG `[Unreleased]` entry; fix `CHANGELOG.md:12` to name the script's
  home repo (`aidoc-flow-ci/sync/check-pin-currency.sh`).
- [ ] **Step 2: Commit** `fix(version): align engine VERSION/__version__ to 0.14.0`.

### Task W6: Reference docs (PR-7, PR-8, PR-9)

- [ ] **Step 1 (PR-7):** `docs/CLI.md` — all 17 verbs (15 `add_parser` calls
  plus the `pause`/`abort` loop) with flags and exit-code
  semantics (0 green / 1 fail / 2 unknown-verb fall-through); rewrite
  `framework/config/CONFIG_CONTRACT.md` per the Approach (real keys +
  reserved section + env-var table + unknown-keys-dropped note).
- [ ] **Step 2 (PR-8):** `docs/OPERATIONS.md` — receiver (`server`) + sync
  how-to with a complete example config (`receiver:` + `iplanic:` blocks),
  credential pairing, heartbeat expectations; add `413 payload_too_large` +
  `404 not_found` rows to REMOTE_EXECUTOR_CONTRACT's response table.
- [ ] **Step 3 (PR-9):** `docs/README.md` index (Diátaxis-grouped: tutorial =
  GETTING_STARTED, how-to = OPERATIONS, reference = CLI + framework
  contracts, explanation = IPLAN-ECOSYSTEM + SECURITY_REVIEW); complete
  `framework/README.md` contents table (`config/`, `effectors/`,
  `handover/`, `intake/`, `remote/`, `security/`, `vcs/`); link the index
  from README.
- [ ] **Step 4: Commit** per PR (`docs(reference): …`); CHANGELOG entries on
  PR-7/PR-8 (they touch `framework/`).

## Verification

> Nothing is "done" until these pass.

```bash
# gate the non-grandfathered plans, PLAN-026 included (the CI pre-commit job
# does exactly this on every PR — the plan must be green at every PR head)
python .claude/skills/verified-planning/check_plan.py \
  $(ls plans/PLAN-0*.md | grep -vE '(^|/)PLAN-0(0[1-9]|1[0-2])_')
pre-commit run --all-files                             # markdownlint (blocking) + all hooks
! grep -qn "v1\.0\.0" docs/SECURITY_REVIEW.md          # no stale version framing
! grep -qn "unimplemented" docs/IPLAN-ECOSYSTEM.md     # gone
! grep -q '\[ \] \*\*B1' TODO.md                       # shipped items checked
cat platforms/hermes/VERSION platforms/claude/VERSION  # 0.14.0 twice
```

Expected:

1. Every doc claim flagged in the review either fixed or explicitly deferred
   in TODO's docs backlog; CI (docs-gate, markdown-lint, plan-gate) green on
   each PR.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Rewriting `plans/HANDOFF.md` / `docs/IPLAN-ECOSYSTEM.md` breaks PLAN-024/PLAN-018 citations (CI plan-gate) | PR-1 repoints PLAN-024's row *before* PR-2/PR-5; rewrites retain the `aidoc-flow-iplanic` literal (PLAN-018 survives on it — no edits); gate PLAN-013+ after each PR |
| R6 | PLAN-026's own ledger cites text this plan deletes; the pre-commit `--all-files` job gates every plan on every PR | Self-ledger strategy in Approach: each deleting PR re-grounds the named PLAN-026 rows in the same PR; PR-7/8/9 designed for symbol survival; `pre-commit run --all-files` green required at every PR head |
| R2 | CONFIG_CONTRACT rewrite could be read as a contract change | Reserved-keys section keeps forward intent explicit; CHANGELOG entry states "documents shipped behavior; no runtime change" |
| R3 | ECOSYSTEM update drifts further from the gated iplanic mirror | W4 only removes false local claims + adds a divergence pointer; no D-0020 content imported |
| R4 | markdownlint (now blocking) rejects new docs | Run `pre-commit run --all-files` before each push |
| R5 | Engine-version bump misread as a release | Commit message + CHANGELOG say metadata alignment to the already-recorded 0.14.0 renumbering (CHANGELOG.md:377) |

## Claim ledger

> Every load-bearing claim cites the `file:line` actually read on 2026-07-19.
> **Snapshot convention:** rows that cite *defective pre-fix text* on
> `main@959287b` lose their symbols by design as fixes land; the deleting PR
> re-grounds those rows in the same PR (see "PLAN-026 self-ledger strategy"
> in Approach — the PR table names the rows per PR). Rows whose symbols
> survive their fix (e.g. 43, 47) remain pre-fix snapshots by design.

| # | Claim | Symbol | Citation |
|---|-------|--------|----------|
| 1 | pre-commit `check-plan` hook gates every non-grandfathered plan on `--all-files` | `id: check-plan` | .pre-commit-config.yaml:58 |
| 2 | B1+B3 shipped (PR #71) | `PLAN-025 P1: clone-URL RCE (B1)` | CHANGELOG.md:75 |
| 3 | M-body + M-budget-parity shipped (PR #72) | `PLAN-025 P3 (batch 1)` | CHANGELOG.md:62 |
| 4 | M-ws + M-relay shipped (PR #73) | `PLAN-025 P3 (batch 2)` | CHANGELOG.md:40 |
| 5 | M-wall shipped (PR #74) | `PLAN-025 P3 (batch 3)` | CHANGELOG.md:26 |
| 6 | ROADMAP header frozen at v0.1.0 | `Slice 1 complete` | ROADMAP.md:6 |
| 7 | ROADMAP names a dead working branch | `claude/iplan-execution-framework-jc03k` | ROADMAP.md:7 |
| 8 | ROADMAP claims repo has no CI | `currently has no CI` | ROADMAP.md:51 |
| 9 | Phase 2 still marked planned | `planned` | ROADMAP.md:81 |
| 10 | G13 claims LICENSE/CONTRIBUTING missing | `not yet added` | ROADMAP.md:181 |
| 11 | CLAUDE.md says canon CI is future | `will consume reusable workflows` | CLAUDE.md:112 |
| 12 | CLAUDE.md per-repo CI state is 2026-06-22/private | `Per-repo state (2026-06-22)` | CLAUDE.md:121 |
| 13 | HANDOFF stamped 2026-06-27 | `Updated **2026-06-27**` | plans/HANDOFF.md:5 |
| 14 | HANDOFF contradicts OPS-0062 merge policy | `Never merge` | plans/HANDOFF.md:123 |
| 15 | HANDOFF says next plan = PLAN-024 | `next **plan** = **PLAN-024**` | plans/HANDOFF.md:135 |
| 16 | PLAN-025 status header stale | `pending independent review` | plans/PLAN-025_preprod-hardening.md:3 |
| 17 | PLAN-024 status header stale | `pending independent review` | plans/PLAN-024_real-executor-client.md:3 |
| 18 | Root HANDOFF.md is CI-test residue | `ai-review + composition verification` | HANDOFF.md:2 |
| 19 | SECURITY_REVIEW framed as v1.0.0 | `Security Review (v1.0.0)` | docs/SECURITY_REVIEW.md:1 |
| 20 | Spec contract version is 0.14.0 | `0.14.0` | framework/VERSION:1 |
| 21 | Engine `__version__` lags at 0.13.0 | `__version__ = "0.13.0"` | `platforms/hermes/src/iplan_hermes/__init__.py:6` |
| 22 | Engine pyproject already 0.14.0 | `version = "0.14.0"` | platforms/hermes/pyproject.toml:7 |
| 23 | Renumbering to pre-1.0 recorded | `Version scheme corrected to pre-1.0` | CHANGELOG.md:377 |
| 24 | ECOSYSTEM claims handoffs not wired | `the handoffs are not wired` | docs/IPLAN-ECOSYSTEM.md:81 |
| 25 | ECOSYSTEM calls PLAN-013 unimplemented | `unimplemented` | docs/IPLAN-ECOSYSTEM.md:82 |
| 26 | PLAN-013 is DONE (implemented) | `DONE - 2026-06-11` | plans/PLAN-013_iplanic-remote-executor-conformance.md:37 |
| 27 | ECOSYSTEM claims identical mirrors | `identical copy` | docs/IPLAN-ECOSYSTEM.md:6 |
| 28 | hermes accepts only mock/api | `want 'mock' or 'api'` | platforms/hermes/src/iplan_hermes/cli/commands.py:193 |
| 29 | claude accepts only mock/host | `want 'mock' or 'host'` | platforms/claude/src/iplan_claude/cli/commands.py:193 |
| 30 | README implies three modes for all | `` `mock` / `host` / `api` `` | README.md:79 |
| 31 | Sync key is nested `sync.enabled` | `"enabled" in sync` | platforms/claude/src/iplan_claude/config.py:77 |
| 32 | GETTING_STARTED snippet has unbound names | `scripted_executor(actions, workspace)` | docs/GETTING_STARTED.md:38 |
| 33 | GETTING_STARTED teaches a private attr | `engine._config.signing_key` | docs/GETTING_STARTED.md:62 |
| 34 | README docs/ row omits ECOSYSTEM | `Getting-started guide + security review` | README.md:119 |
| 35 | CLI verb surface starts at `ledger` | `add_parser("ledger"` | platforms/claude/src/iplan_claude/cli/commands.py:47 |
| 36 | CLI exits 2 on unknown verbs (argparse-rejected; `return 2` is the defensive fall-through) | `return 2` | platforms/claude/src/iplan_claude/cli/commands.py:436 |
| 37 | CONFIG_CONTRACT documents unshipped `budget` | `max_cost_usd` | framework/config/CONFIG_CONTRACT.md:15 |
| 38 | CONFIG_CONTRACT documents unshipped telemetry key | `telemetry.otlp_endpoint` | framework/config/CONFIG_CONTRACT.md:16 |
| 39 | Real config has a `receiver.*` block | `receiver_enabled` | platforms/claude/src/iplan_claude/config.py:39 |
| 40 | `load_config` drops unknown keys silently | `if key in fields` | platforms/claude/src/iplan_claude/config.py:71 |
| 41 | Receiver returns 413 | `request body too large` | platforms/claude/src/iplan_claude/receiver/http.py:52 |
| 42 | Receiver returns 404 | `not_found` | platforms/claude/src/iplan_claude/receiver/http.py:84 |
| 43 | Contract response table lacks 413/404 rows | `503 receiver_busy` | framework/remote/REMOTE_EXECUTOR_CONTRACT.md:99 |
| 44 | `IOPS_RELAY_RETENTION_S` is a shipped env knob | `IOPS_RELAY_RETENTION_S` | platforms/hermes/src/iplan_hermes/relay/store.py:38 |
| 45 | `IOPS_INSECURE_CLONE_SCHEMES` is a shipped env knob | `IOPS_INSECURE_CLONE_SCHEMES` | platforms/hermes/src/iplan_hermes/validation/payload_rules.py:37 |
| 46 | Signing key comes from `IOPS_SIGNING_KEY` | `IOPS_SIGNING_KEY` | platforms/claude/src/iplan_claude/config.py:101 |
| 47 | framework/README table ends at conformance (7 dirs missing) | `conformance/vectors/` | framework/README.md:23 |
| 48 | CHANGELOG cites a script that lives in aidoc-flow-ci, not here | `check-pin-currency.sh` | CHANGELOG.md:12 |
| 49 | `IOPS_SECRET_*` prefix redaction is shipped | `IOPS_SECRET_` | platforms/claude/src/iplan_claude/config.py:52 |
| 50 | `IOPS_IPLANIC_TOKEN` is the default sync-token env | `IOPS_IPLANIC_TOKEN` | platforms/claude/src/iplan_claude/config.py:36 |
| 51 | `IOPS_RECEIVER_TOKEN` is the default receiver-auth env | `IOPS_RECEIVER_TOKEN` | platforms/claude/src/iplan_claude/config.py:42 |
| 52 | PLAN-024 cites HANDOFF:134 (the row PR-1 repoints) | `plans/HANDOFF.md:134` | plans/PLAN-024_real-executor-client.md:102 |
| 53 | PLAN-018 cites HANDOFF:96 via `aidoc-flow-iplanic` | `plans/HANDOFF.md:96` | plans/PLAN-018_oss-public-migration.md:513 |
| 54 | CI grandfathers PLAN-001..012 by filename only | `1[0-2])_` | .github/workflows/plan-gate.yml:24 |
| 55 | docs-gate fires on any `framework/` touch | `^framework/` | tests/chg/docs_gate.py:32 |
| 56 | `pause`/`abort` verbs come from a loop (17 verbs total) | `("pause", "abort")` | platforms/claude/src/iplan_claude/cli/commands.py:109 |
| 57 | Phases 11–12 already read done in ROADMAP | `plans/PLAN-011` | ROADMAP.md:157 |
| 58 | pre-commit CI runs `--all-files` on every push/PR | `pre-commit run --all-files` | .github/workflows/pre-commit.yml:31 |

## Review log

### Pass 1 - 2026-07-19

- Author pass over the assembled findings: dropped the cross-repo iplanic
  citation from the ledger (CI plan-gate has no sibling checkout; the
  divergence claim is carried by the runner-local `identical copy` rows 26–27
  plus prose); moved CHANGELOG release-header restructuring (consistency
  finding) from In-scope to Out with rationale; added the R1 citation-shift
  guard after re-reading the HANDOFF CI-gotcha note; split W1 into two PRs to
  honor governance Rule 1 (was one 5-surface PR).

### Pass 2 - 2026-07-19 - independent

Fresh-context adversarial reviewer verified all 47 (then-)ledger rows true on
`main@959287b`, and returned 6 load-bearing + 4 minor findings — all folded:

- Verification command `check_plan.py plans/PLAN-0*.md` fails on main
  (PLAN-001..012 grandfathered only in CI) → command now filters to PLAN-013+.
- PLAN-026's own ledger cites text the plan deletes; `--fix` cannot repair
  deleted symbols → snapshot convention + PR-10 re-grounding added (R6).
- PR-9 misses docs-gate (`framework/README.md` touch) → CHANGELOG added.
- PLAN-024's HANDOFF citation is `:134` (at PLAN-024:102), not `:135`, and
  PLAN-018 rows 10–12 (`aidoc-flow-iplanic`) were unguarded → guard rewritten,
  rows 52–53 added.
- PLAN-025 open list omitted P5 → "P2/P4/P5/P6 open" + PR-2-executes-P5 note.
- PR-2's `--fix` on PLAN-018 would breach Rule 1 → PR-1 absorbs plan-file
  hardening; PR-2 makes no plan-file edits.
- Minor: verb count 17 not 16; W2 range 2–10 not 2–12; `grep -c` → `! grep -q`;
  missing ledger rows for CHANGELOG:12 + env vars → rows 48–51, 54–57 added.

### Pass 3 - 2026-07-19 - independent

Second fresh-context reviewer verified all 57 ledger rows clean (0 misses, 0
drifts) and returned 2 load-bearing + 4 minor findings — all folded:

- **The self-ledger strategy was broken:** the pre-commit CI job
  (`pre-commit.yml:31`, `--all-files`) runs the `check-plan` hook over every
  non-grandfathered plan on every PR, so "latent-red until PR-10" would fail
  CI from PR-2 onward → restructured: each deleting PR re-grounds the named
  PLAN-026 rows in-PR; PR slicing re-balanced (TODO sync → PR-A; PR-5 split
  into 5a/5b; PR-7/8/9 designed for symbol survival); rows 1 + 58 added.
- **PLAN-025 status wording would ship a new inaccuracy:** P3 is 5/7 landed
  (M-crash, M-rotation open), not "P3 landed" → Step 1 wording fixed.
- Minor: "filter exists only in CI" corrected (also in the pre-commit hook
  config); docs-gate citation aligned to `:32`; row 36 mechanism reworded
  (argparse rejects unknown verbs; `return 2` is the fall-through); noted the
  gate's zero-findings phrase requirement for the final pass.

### Pass 4 - 2026-07-19 - independent

Third fresh-context reviewer machine- and semantically verified all 58 ledger
rows (0 errors, 0 drifts; ~45 rows semantically checked incl. all recent
additions), confirmed the self-ledger strategy against the real gate
mechanics, the per-PR row lists, and the Rule 1 math. Two load-bearing
wording defects + four minors, all folded in-pass:

- A stale pre-restructure sentence ("PR-2 makes no plan-file edits")
  contradicted the PR table → reworded (PR-2's only plan-file edit is the
  PLAN-026 re-ground).
- PR-1's survival of rows 16/17/52/53 rested on undocumented duplicate
  symbols, and the "harden PLAN-018" instruction could kill row 53 →
  PLAN-018 is now explicitly untouched; the duplicate-symbol reliance is
  named on the PR-1 row.
- Minors: snapshot convention extended to symbol-surviving rows (43/47);
  File Structure gained the PLAN-026 self-edit row; SECURITY_REVIEW step
  names all three `v1.0.0` occurrences; Status/Pass-4 reconciliation noted.

Reviewer re-confirmed after the folds: the two load-bearing findings are
resolved; no new findings. **Result:** ready.
