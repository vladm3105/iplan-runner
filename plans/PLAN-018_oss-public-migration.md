# OSS Public Migration Implementation Plan

> Development plans follow the SDD workflow inherited from
> `aidoc-flow-framework`: **plan → review (≥2 passes) → implement → verify →
> land**. A plan needs at least two review passes recorded in `## Review log`
> before it may be implemented; harden until a pass finds nothing.

**Goal:** Make `iplan-runner` ready to flip from private to public on GitHub,
mirroring the already-public `aidoc-flow-framework`, with no secrets/PII exposed
and standard open-source community-health files in place.

**Architecture:** Repo-level change only. No `framework/` contract or
`platforms/<engine>/` runtime code changes. Touches licensing, `.github/`
community-health files, doc hygiene, git history, and (final, gated) GitHub repo
settings.

**Tech Stack:** Markdown, YAML (GitHub Actions / dependabot), git, `gitleaks`,
`detect-secrets`, GitHub repo settings.

---

| Field      | Value |
|------------|-------|
| Task       | OSS-PUB-018 |
| Depends on | `aidoc-flow-framework` (public reference); `plans/PLAN-017` (latest plan) |
| Status     | DONE (Tasks 1–6 executed; repo is public) - 2026-06-15 |
| Feeds      | Public release of `iplan-runner`; aligns the suite's OSS posture |

## Objective

`iplan-runner` is the execution/operations plane companion to the public
`aidoc-flow-framework` and is intended to be public (README is already framed as
"OSS IPLAN executor"). It is currently a **private** GitHub repo. This plan
brings it to public-launch readiness: license alignment, the community-health
files the public framework already has, removal of local-environment leakage, a
clean published history, and a documented (but **not executed**) flip procedure
with verification gates.

**Scope decisions (ratified by maintainer, 2026-06-14):**

- **This session is plan-only.** No GitHub changes are made here.
- **License:** align Apache-2.0 → **MIT** to match the public framework sibling.
- **History:** **squash to a single fresh initial commit** before publishing.
- **Curation:** keep planning artifacts (`plans/`, `docs/`, `.claude/`) public,
  matching the framework's transparency norm.

## Scope

**In:**

1. License swap Apache-2.0 → MIT (G1).
2. Add community-health files the public framework has and this repo lacks:
   `CODEOWNERS`, `PULL_REQUEST_TEMPLATE.md`, `ISSUE_TEMPLATE/`, labeler
   (`.github/labeler.yml` + `.github/workflows/labeler.yml`), and
   `CODE_OF_CONDUCT.md` (G2).
3. Doc hygiene: remove local absolute-path leakage (G3); soften links to
   still-private sibling repos (G4).
4. README badges (G7).
4a. **Curate** the private-monorepo map + internal product/business strategy out
   of the public tree (G8) — remove the verified-planning skill's dev
   PLAN.md/DESIGN.md and `plans/PLAN-016`; redact AIOps-Flow/BRAND/cross-repo
   passages from `plans/DECISIONS.md`, `docs/HANDOFF.md`, `docs/IPLAN-ECOSYSTEM.md`,
   `CHANGELOG.md`, `plans/PLAN-001`.
5. SHA-pin all GitHub Actions, improving on the framework's tag-pinning (G6).
6. Pre-flight security/CI verification gates (run before any flip).
7. Documented, **gated, not-executed** publish procedure: history squash,
   submodule re-pin, branch cleanup, the visibility flip, and post-flip repo
   settings (G5).

**Out:**

1. Any change to `framework/` contract or `platforms/<engine>/src/` code.
2. Touching the already-public `aidoc-flow-framework` repo (its own
   improvements — F1–F5 below — are a separate optional follow-up plan).
3. Actually flipping the repo to public (a later, explicitly authorized step).
4. Publishing engines to PyPI (root `pyproject.toml` is tooling-only; not in
   scope).

## Approach

The repo is already ~85% OSS-ready. CI is fork-safe and security tooling is
strong, so the work is additive hardening + hygiene, not restructuring.

**Already good (verified, no work):** Apache LICENSE present;
README/ROADMAP/CHANGELOG/CONTRIBUTING/SECURITY.md/TODO present; six CI workflows
with least-privilege `permissions: contents: read`, plain `pull_request`
triggers (no `pull_request_target`), and no `secrets.*` usage; `gitleaks detect`
runs on **full history** in CI; weekly `pip-audit`; CodeQL; pre-commit;
detect-secrets baseline; `dependabot.yml` already covering **both** engines +
conformance + github-actions (more complete than the framework's). `framework/`
is vendored (tracked files, not a submodule), so it clones cleanly when public.
A pattern scan of full history this session surfaced no plaintext secrets (only
detect-secrets baseline hashes); the **authoritative** secret gate is CI
`gitleaks detect` (already wired) re-run as a hard pre-flip gate (Task 6 Step 1,
R3) — `gitleaks` is not installed in this planning environment, so the in-session
scan is corroborating, not authoritative. No workflow uses `pull_request_target`
or `secrets.*` (verified by grep across all six workflows this session; see
Verification).

**Reference comparison.** `aidoc-flow-framework` is already public (MIT,
verified via `gh` API this session: `visibility=public`, `license=MIT`). The
concrete community-health files it has and this repo lacks are `CODEOWNERS`,
`PULL_REQUEST_TEMPLATE.md`, `ISSUE_TEMPLATE/`, and labeler config — these are
copied/adapted in G2. The framework SHA pins nothing (tag-pinned `@v6`/`@v4`);
G6 improves on that here.

**Framework-side improvements (out of scope, recommended follow-up):**

| # | Framework finding | Note |
|---|-------------------|------|
| F1 | Actions tag-pinned, not SHA-pinned | hardening |
| F2 | No `CODE_OF_CONDUCT.md` | OSS health |
| F3 | Local abs-path leaks committed in the **public** repo (`CHANGELOG.md`, `plans/HANDOFF.md`, many `plans/*`) | live info-disclosure/hygiene |
| F4 | No README badges | polish |
| F5 | `dependabot.yml` misses `platforms/claude` | coverage |

**Decision cross-references:** this plan introduces no new architecture; it does
not alter any `plans/DECISIONS.md` entry.

## File Structure

| Path | Responsibility |
|------|----------------|
| `LICENSE` | Replace Apache-2.0 text with MIT (G1) |
| `CODE_OF_CONDUCT.md` | New — Contributor Covenant (G2) |
| `.github/CODEOWNERS` | New — review auto-assignment (G2) |
| `.github/PULL_REQUEST_TEMPLATE.md` | New — PR checklist (G2) |
| `.github/ISSUE_TEMPLATE/` | New — bug/feature/security templates + `config.yml` (G2) |
| `.github/labeler.yml` | New — path→label map (G2) |
| `.github/workflows/labeler.yml` | New — auto-label workflow, fork-safe (G2) |
| `.github/workflows/*.yml` | Edit — SHA-pin all `uses:` actions (G6) |
| `README.md` | Edit — add badges; any license reference → MIT (G1, G7) |
| `docs/HANDOFF.md`, `docs/IPLAN-ECOSYSTEM.md` | Edit — path leak + private-link softening (G3, G4) |
| `.claude/skills/verified-planning/PLAN.md` | Edit — genericize local path (G3) |
| `plans/HANDOFF.md` | Edit — soften private-repo references (G4) |
| `plans/PLAN-018_oss-public-migration.md` | This plan |

## Step Sequence

> Each task is one commit. The history squash (Task 6) is a publish-time
> operation, executed only when the maintainer authorizes the flip.

### Task 1: License alignment (G1)

**Files:** Modify `LICENSE`, `README.md`

- [ ] **Step 1: Replace LICENSE body with MIT**

  Replace the Apache-2.0 text (`LICENSE:2` "Apache License") with the standard
  MIT License text, copyright holder and year matching the framework's
  `LICENSE`. Update any "Apache" reference in `README.md` to "MIT".

- [ ] **Step 2: Commit**

  ```bash
  git add LICENSE README.md
  git commit -m "chore: relicense iplan-runner Apache-2.0 -> MIT to match suite"
  ```

### Task 2: Community-health files (G2)

**Files:** Create `CODE_OF_CONDUCT.md`, `.github/CODEOWNERS`,
`.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/*`,
`.github/labeler.yml`, `.github/workflows/labeler.yml`

- [ ] **Step 1: CODE_OF_CONDUCT.md** — Contributor Covenant v2.1, contact set to
  the SECURITY.md reporting channel.

- [ ] **Step 2: CODEOWNERS** — adapt the framework's
  (`.github/CODEOWNERS:1`); map `framework/`, `platforms/hermes/`,
  `platforms/claude/`, `tests/`, `plans/`, `docs/` to the maintainer.

- [ ] **Step 3: PULL_REQUEST_TEMPLATE.md** — adapt the framework's
  (`.github/PULL_REQUEST_TEMPLATE.md:1`); keep the repo's CHANGELOG / docs-gate
  expectations as checklist items.

- [ ] **Step 4: ISSUE_TEMPLATE/** — adapt the relevant subset of the framework's
  set (`.github/ISSUE_TEMPLATE/bug_report.md:1`): `bug_report.md`,
  `feature_request.md`, `security_report.md`, and `config.yml` pointing security
  reports to private vulnerability reporting (per `SECURITY.md`).

- [ ] **Step 5: labeler** — adapt the framework's `.github/labeler.yml:1` to
  this repo's paths and `.github/workflows/labeler.yml:4` (plain
  `pull_request`, `permissions: contents: read` + `pull-requests: write`,
  concurrency — fork-safe, no `pull_request_target`). Note: labels referenced
  must be created in the repo before the workflow can apply them.

- [ ] **Step 6: Commit**

  ```bash
  git add CODE_OF_CONDUCT.md .github/CODEOWNERS .github/PULL_REQUEST_TEMPLATE.md \
          .github/ISSUE_TEMPLATE .github/labeler.yml .github/workflows/labeler.yml
  git commit -m "chore(github): add community-health files (CoC, CODEOWNERS, templates, labeler)"
  ```

### Task 3: SHA-pin GitHub Actions (G6)

**Files:** Modify `.github/workflows/*.yml`

- [ ] **Step 1: Pin every `uses:`** to a full commit SHA with a trailing
  `# vX.Y.Z` comment, for `actions/checkout`, `actions/setup-python`,
  `github/codeql-action/*`, `actions/labeler`, and any other action. Resolve
  each SHA from the action's release tag.

- [ ] **Step 2: Pin the gitleaks binary download by checksum.** `security.yml`
  installs gitleaks via an unauthenticated `curl` of a release tarball
  (`security.yml:58`). On a public repo this runs on fork PRs; add a
  `sha256sum -c` verification of the downloaded tarball against the pinned
  release checksum before `install`, so a compromised/MITM'd artifact can't
  execute in CI. (No secret is exposed today — the job has `contents: read` and
  no `secrets.*` — so this is defense-in-depth.)

- [ ] **Step 3: Commit**

  ```bash
  git add .github/workflows
  git commit -m "ci: pin Actions to SHAs + verify gitleaks binary checksum (supply-chain hardening)"
  ```

### Task 4: Doc hygiene — path leaks (G3)

**Files:** Modify `docs/HANDOFF.md`, `.claude/skills/verified-planning/PLAN.md`

- [ ] **Step 1: Genericize ALL local absolute paths.** Replace every
  `/opt/data/...` and `/home/...` with repo-relative or placeholder forms
  (`<workspace>/…`). Complete list (verified by grep this session):
  - `docs/HANDOFF.md:81` (`/opt/data/aidoc-flow/iplanic`)
  - `.claude/skills/verified-planning/PLAN.md` lines **634, 696, 699, 711, 715,
    784** (six hits, incl. `/opt/data/aidoc-flow/iops-framework` and
    `/home/ya/.git`).

- [ ] **Step 2: Genericize the internal SSH remote line.** `docs/HANDOFF.md:10`
  carries `git@github.com:vladm3105/iplan-runner.git` — replace with the public
  HTTPS URL. (Note: the owner handle `vladm3105` itself is the public repo owner
  and is acceptable to keep; only the internal-facing SSH remote is noise.)

- [ ] **Step 3: Commit**

  ```bash
  git add docs/HANDOFF.md .claude/skills/verified-planning/PLAN.md
  git commit -m "docs: remove local absolute-path references [no-changelog]"
  ```

- [ ] **Step 4: Re-run the gate** `git grep -nE '/opt/data/|/home/[a-z]+/' --
  docs/ .claude/ plans/ README.md ':!plans/PLAN-018*'` returns nothing.
  **PLAN-018 is exempt from its own gate**: as the migration's own procedure it
  necessarily contains the search pattern, the `git grep` gate text, and
  leak-location documentation. It carries no *environment* leak beyond those
  self-references; the relative `../framework` form is used elsewhere to keep the
  footprint minimal.

- [ ] **Step 5: Harden `.gitignore` (publication-surface defense-in-depth).** The
  root `.gitignore` covers `__pycache__/`, `*.py[cod]`, `tmp/`, IDE dirs, but
  **not** `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/` — these exist in the
  working tree and are only kept out today by each tool's auto-written nested
  `.gitignore` (fragile). Add explicit entries so the Task 6 squash's `git add
  -A` can never stage local cache/scratch. Commit:

  ```bash
  printf '\n# Tool caches\n.mypy_cache/\n.ruff_cache/\n.pytest_cache/\n' >> .gitignore
  git add .gitignore && git commit -m "chore: ignore tool caches before public squash [no-changelog]"
  ```

### Task 5: Doc hygiene + curation — links, badges, private disclosure (G4, G7, G8)

**Files:** Modify `docs/IPLAN-ECOSYSTEM.md`, `plans/HANDOFF.md`, `README.md`,
`plans/DECISIONS.md`, `docs/HANDOFF.md`, `CHANGELOG.md`, `plans/PLAN-001`;
**remove** `.claude/skills/verified-planning/PLAN.md`,
`.claude/skills/verified-planning/DESIGN.md`,
`plans/PLAN-016_codename-reassign-and-iplan-package-rename.md`

- [ ] **Step 1: Soften ALL `aidoc-flow-iplanic` references.** Annotate every
  reference as "(private — planned public)" instead of broken links, keeping them
  as forward-references. Complete list (verified by grep this session):
  `docs/IPLAN-ECOSYSTEM.md:15`, `docs/IPLAN-ECOSYSTEM.md:98`,
  `plans/HANDOFF.md:31`, `plans/HANDOFF.md:71`, `plans/HANDOFF.md:88`.

- [ ] **Step 2: README badges (G7).** Add CI, license (MIT), and
  framework-version badges to `README.md`, mirroring standard OSS placement.

- [ ] **Step 3: G8 — curate private monorepo map + business strategy
  (maintainer decision: curate before public).**

  **Remove from the public tree** (internal-strategy / dev artifacts; engineering
  value not needed in the OSS repo):
  - `.claude/skills/verified-planning/PLAN.md` and `DESIGN.md` — they enumerate
    all six private repos. **Keep** the actual tool: `SKILL.md`, `check_plan.py`,
    `PLAN-TEMPLATE.snippet.md`, `install.sh`, `plan-gate.yml`,
    `precommit-hook.snippet.yaml`, and `tests/` (verify `tests/test_check_plan.py`
    + `tests/test_install.sh` carry no sibling-repo names; genericize if they do).
  - `plans/PLAN-016_codename-reassign-and-iplan-package-rename.md` — wholly
    AIOps-Flow/brand/cross-repo business strategy; cannot be de-internalized.

  **Redact internal product/governance passages** (keep the file, remove the
  strategy content — replace with a neutral one-line summary where a decision
  must remain referenced):
  - `plans/DECISIONS.md` — D-0019 and any text binding AIOps-Flow /
    `BRAND_AND_DOMAINS.md` / `business/` / `operations/` consolidation. **Also
    remove path-form repo-map references** (e.g. "the `operations` repo",
    `business/docs/DECISIONS.md`) — these disclose the private layout without
    containing any of the gate tokens.
  - `docs/HANDOFF.md`, `CHANGELOG.md` — AIOps-Flow / `iops-framework` /
    cross-repo strategy mentions (incl. path-form repo refs).
    (`docs/IPLAN-ECOSYSTEM.md` is **not** a G8 target — its only sensitive
    reference is `aidoc-flow-iplanic`, owned by G4 Step 1.)
  - `plans/PLAN-001` — replace the old `aidoc-flow-iops-framework` repo/codename
    references with `iplan-runner`.

- [ ] **Step 4: G8 gate — no private-monorepo or internal-product tokens remain.**

  ```bash
  # must return nothing (PLAN-018 exempt; engineering uses of the English words
  # "business"/"operations" are fine — these tokens are the load-bearing leaks):
  ! git grep -nIE 'iops-framework|AIOps-Flow|BRAND_AND_DOMAINS|knowledge-rag' -- . ':!plans/PLAN-018*'
  ! git grep -nIE '(business|operations)/(docs|ops|src|plans)/' -- . ':!plans/PLAN-018*'   # path-form repo-map leak
  ! git ls-files | grep -E 'verified-planning/(PLAN|DESIGN)\.md$|PLAN-016'
  ```

- [ ] **Step 5: Commit**

  ```bash
  git rm .claude/skills/verified-planning/PLAN.md .claude/skills/verified-planning/DESIGN.md \
         plans/PLAN-016_codename-reassign-and-iplan-package-rename.md
  git add docs/ plans/ README.md CHANGELOG.md
  git commit -m "docs: curate private-monorepo map + business strategy before public (G8) [no-changelog]"
  ```

### Task 6: Publish procedure — GATED, executed only on explicit authorization

> Nothing in this task runs in the plan-only session. It documents the flip.

- [ ] **Step 1: Consolidate the canonical tree onto `main` FIRST.** ⚠️ The repo
  is currently on `docs/per-repo-governance` (`515ec8b`), which is **ahead of**
  `main` (`8cd491e`); Tasks 1–5 above also add commits. Before any squash,
  merge/land **all wanted branches into `main`** so `main` is the single source
  of truth: the Tasks 1–5 work, `docs/per-repo-governance`, and any keepers from
  `chore/pre-commit-and-working-changes` /
  `claude/iplan-execution-framework-jc03k`. Then delete those branches and close
  their PRs. **Do not squash from any branch other than the consolidated `main`.**

- [ ] **Step 2: Pre-flight gates (must all pass) — run on consolidated `main`.**

  ```bash
  git checkout main
  gitleaks detect --source . --redact --no-banner --verbose   # history scan (corroborating; squash discards history — Step 3d is authoritative)
  detect-secrets scan --baseline .secrets.baseline            # no new secrets vs baseline
  # CI green on main (conformance + engines + lint + codeql + security)
  ```

- [ ] **Step 3: History squash to fresh start.** Collapse `main` to a single
  root commit. **Security-critical:** the squash makes this one commit the entire
  public surface — all prior history (and any secret ever committed and later
  removed) is discarded by construction. The flip side is that `git add -A`
  stages **every untracked, non-ignored file in the working tree**, so it must
  not run against a dirty checkout.

  ```bash
  git checkout main
  # (a) HARDEN .gitignore first so caches/scratch can never be staged (see Task 4 Step 5).
  # (b) Inspect EXACTLY what would be published — must be tracked files + intended new files only:
  git add -An                                 # dry-run; review every line
  git status --ignored --porcelain | grep '^!!' | head   # sanity-check what is ignored
  # (c) Build the orphan from the reviewed tree:
  git checkout --orphan public-main           # orphan FROM the consolidated main tree
  git add -A && git status --short            # final visual confirm before commit
  git commit -m "iplan-runner v1.0.0 — OSS IPLAN executor"
  # (d) AUTHORITATIVE secret gate on the ACTUAL published artifact (the squashed tree):
  gitleaks detect --source . --redact --no-banner --verbose   # must exit 0
  git branch -M public-main main
  # NOTE: after -M, local main shares no ancestry with origin/main, so
  # --force-with-lease degenerates to --force. Fetch + eyeball origin/main first.
  git push --force origin main
  ```

- [ ] **Step 4: Re-pin the super-repo submodule EXPLICITLY.** `iplan-runner` is a
  submodule of the private `aidoc-flow` super-repo; the current gitlink
  (`3f4ad01`) is **not an ancestor of the squashed `main`**, so
  `git submodule update --remote` will **not** reliably re-point it. Set the
  gitlink directly to the new `main` HEAD:

  ```bash
  cd <workspace>/aidoc-flow
  git -C iplan-runner fetch origin && git -C iplan-runner checkout main
  git -C iplan-runner reset --hard origin/main
  git add iplan-runner
  git commit -m "chore(submodule): re-pin iplan-runner to squashed public main"
  ```

- [ ] **Step 5: Flip visibility + settings (GitHub UI / API).**
  - Settings → Danger Zone → Change visibility → **Public**.
  - Enable **branch protection** on `main` (require PR + status checks:
    conformance/engines/lint/codeql/security).
  - Security & analysis: enable **private vulnerability reporting**, Dependabot
    alerts + security updates, secret scanning + push protection. (Push
    protection only applies once public/GHAS-enabled; the pre-flip authoritative
    secret gate is Step 2's `gitleaks detect`.)
  - Set repo **description** and **topics** to match the framework's.

## Verification

> Nothing is "done" until these pass.

```bash
# Plan-quality gate (matches the repo's check-plan pre-commit hook):
python .claude/skills/verified-planning/check_plan.py \
  plans/PLAN-018_oss-public-migration.md

# After Tasks 1–5 (pre-flip readiness):
test "$(grep -c 'MIT License' LICENSE)" -ge 1                       # G1
ls CODE_OF_CONDUCT.md .github/CODEOWNERS .github/PULL_REQUEST_TEMPLATE.md \
   .github/labeler.yml .github/workflows/labeler.yml                 # G2
! git grep -nE '/opt/data/|/home/[a-z]+/' -- docs/ .claude/ plans/ ':!plans/PLAN-018*'  # G3 (plan exempt; see Task 4 Step 4)
! grep -rnE 'uses: [^#]+@v[0-9]+\s*$' .github/workflows               # G6 (all SHA-pinned)
! grep -rnE 'pull_request_target|secrets\.' .github/workflows         # no elevated triggers/secret use
! git grep -nIE 'iops-framework|AIOps-Flow|BRAND_AND_DOMAINS|knowledge-rag' -- . ':!plans/PLAN-018*'  # G8 tokens
! git grep -nIE '(business|operations)/(docs|ops|src|plans)/' -- . ':!plans/PLAN-018*'  # G8 path-form repo-map
! git ls-files | grep -E 'verified-planning/(PLAN|DESIGN)\.md$|PLAN-016'  # G8 removed files
gitleaks detect --source . --redact --no-banner                      # secrets clean
```

Expected:

1. `check_plan.py` prints `ok … verified N citation(s), M review pass(es)`.
2. LICENSE is MIT; all G2 files exist; no local-path leaks; every action
   SHA-pinned; gitleaks reports no findings.

## Security review (publication surface)

A hands-on scan of the working tree (the exact bytes the squash will publish) was
run this session. Findings:

- **No live secrets / credentials.** Broad pattern scan (AWS/GCP/Slack/GitHub
  PAT/JWT/PEM/OpenAI) of all tracked files: zero hits. No `.env`, `.pem`, `.key`,
  `.npmrc`, `.pypirc`, or keystore tracked (only `.secrets.baseline`).
- **`.secrets.baseline` flags are fake test fixtures**, not real secrets:
  `platforms/{hermes,claude}/tests/test_budget.py` uses obvious dummy values
  (a `SHOULD_BE_IGNORED` placeholder signing key and throwaway `IOPS_SECRET_*`
  env vars) to assert config behaviour. Safe to publish.
- **`.claude/` carries no local config/tokens** — it holds only the
  `verified-planning` skill (no `settings.local.json`, no MCP credentials).
- **No infra disclosure** — no enterprise hosts, internal IPs, `techtrend`, or
  CI/registry hostnames in tracked files.
- **⚠️ BLOCKING — private monorepo + business-strategy disclosure (G8).** Tracked
  files that the curation decision keeps public reference the *other* private
  sibling repos by bare name and expose internal product/governance strategy.
  This was missed by the initial scan (which searched only the `aidoc-flow-`
  prefix). Surfaces:
  - **Private-repo map:** `.claude/skills/verified-planning/PLAN.md` (lines
    635/651/670/675/698 — `for r in framework iops-framework business operations
    iplanic knowledge-rag`) and `.claude/skills/verified-planning/DESIGN.md:137`
    enumerate all six private repos and which adopted the gate.
  - **Product/business strategy:** `plans/PLAN-016` (codename → **AIOps-Flow**
    product, `BRAND_AND_DOMAINS.md`, cross-repo PR plans in `business/` +
    `operations/`), `plans/DECISIONS.md` (D-0019 product/governance bindings),
    plus refs in `docs/HANDOFF.md`, `docs/IPLAN-ECOSYSTEM.md`, `CHANGELOG.md`.
  - **Severity:** info-disclosure (CWE-200), irreversible once public.
  - **Resolution (maintainer decision 2026-06-14: curate before public):** Task 5
    G8 removes the dev artifacts + `PLAN-016` and redacts strategy passages, gated
    by the G8 check in Verification.
- **PII:** the only email-shaped token is the SSH remote
  `git@github.com:vladm3105/...` (`docs/HANDOFF.md:10`, handled by Task 4 Step 2).
  The squash commit will carry the committer identity `vl.myakota@gmail.com` —
  the owner's public email; acceptable by the owner's choice (swap to a GitHub
  `noreply` address at squash time if undesired).
- **Squash = history-secret elimination by construction.** Because the published
  repo is a single orphan commit of the current tree, no past commit (or any
  secret ever committed and later removed) is reachable. The residual risk is
  therefore the *tree*, gated by Task 6 Step 3(d) `gitleaks detect` on the
  squashed artifact.
- **`git add -A` footprint** is the main publication-surface hazard: it stages
  every untracked, non-ignored file. Verified today it would stage only this
  plan (caches self-ignore), but that is fragile → Task 4 Step 5 hardens
  `.gitignore` and Step 3 adds a dry-run + final visual confirm.
- **CI is safe to expose:** all six workflows use `permissions: contents: read`,
  plain `pull_request` (no `pull_request_target`), and zero `secrets.*`; the one
  unauthenticated binary download is hardened by Task 3 Step 2.

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Squash orphans open PRs / breaks contributor forks | Task 6 Step 2 lands+closes all branches/PRs before the squash; squash is a one-time pre-public event |
| R2 | Super-repo submodule gitlink points at a dead SHA after squash | Task 6 Step 4 re-pins the `aidoc-flow` super-repo pointer in the same change window |
| R3 | A secret exists in history that pattern scans missed | CI already runs `gitleaks detect` on full history; Task 6 Step 1 re-runs gitleaks + detect-secrets as a hard gate before the flip |
| R4 | Relicensing requires consent of all copyright holders | Single-maintainer repo (CODEOWNERS = maintainer); confirm no external contributors before relicense |
| R5 | Softened private links still 404 if `aidoc-flow-iplanic` stays private | Annotated as "(private — planned public)" rather than live links; revisit when iplanic opens |
| R6 | Labeler workflow fails until labels exist | Documented in Task 2 Step 5; create labels at flip time |
| R7 | Squash `git add -A` publishes untracked local cache/scratch files | Task 4 Step 5 hardens `.gitignore`; Task 6 Step 3 adds `git add -An` dry-run + `git status --short` confirm + post-squash `gitleaks detect` |
| R8 | CI fork PR runs an unauthenticated gitleaks binary download (supply chain) | Task 3 Step 2 verifies the tarball `sha256sum`; job already has `contents: read` and no `secrets.*` |
| R9 | Public tree disclosed the private-repo map + AIOps-Flow/business strategy (CWE-200) | Task 5 G8 (Steps 3–5) removes the dev artifacts + `PLAN-016` and redacts strategy passages; G8 gate proves the tokens are gone before squash |

## Claim ledger

> Every load-bearing claim cites the `file:line` actually read. Citations
> All rows resolve in **this** repo (so the repo's `check-plan` pre-commit hook
> passes without `--root`). Framework-comparison facts (what the public framework
> has that this repo adapts in G2/G6) live in the Approach narrative and were
> verified in `../framework` this session. (Row 8 cites this repo's *vendored*
> `framework/VERSION`, proving it is tracked, not a submodule.)

| # | Claim | Symbol | Citation |
|---|-------|--------|----------|
| 1 | License is MIT (G1 relicensed from Apache-2.0; executed) | `MIT License` | LICENSE:1 |
| 2 | README already frames the repo as OSS | `# iplan-runner — OSS IPLAN executor` | README.md:1 |
| 3 | CI uses least-privilege token | `contents: read` | .github/workflows/ci.yml:9 |
| 4 | CI trigger is plain `pull_request` (no `pull_request_target`) | `pull_request:` | .github/workflows/ci.yml:6 |
| 5 | Secret scan runs on full git history in CI | `gitleaks detect` | .github/workflows/security.yml:64 |
| 6 | Full-history fetch enables the scan | `fetch-depth: 0` | .github/workflows/security.yml:48 |
| 7 | Weekly dependency audit present | `pip-audit` | .github/workflows/security.yml:40 |
| 8 | `framework/` is vendored as tracked files (not a submodule) | `0.14.0` | framework/VERSION:1 |
| 9 | dependabot already covers the `claude` engine | `directory: /platforms/claude` | .github/dependabot.yml:10 |
| 10 | Private sibling referenced in ecosystem doc (404 risk) | `aidoc-flow-iplanic` | docs/IPLAN-ECOSYSTEM.md:15 |
| 11 | Private sibling referenced in handoff doc (softened, G4) | `aidoc-flow-iplanic` | plans/HANDOFF.md:92 |
| 12 | Path leak genericized to the repo name (G3; executed) | `aidoc-flow-iplanic` | plans/HANDOFF.md:92 |
| 13 | Latest existing plan is PLAN-017 (this is 018) | `PLAN-017` | plans/PLAN-017_d4-iplanic-transport-design.md:1 |
| 14 | Root pyproject is tooling-only (no `[project]`, not a PyPI package) | `[tool.ruff]` | pyproject.toml:1 |
| 15 | A second workflow also uses a least-privilege token (witness for the cross-workflow safety claim; exhaustive check is the grep gate in Verification) | `permissions:` | .github/workflows/codeql.yml:11 |
| 16 | Baselined "secrets" are fake test fixtures, not real credentials | `SHOULD_BE_IGNORED` | platforms/hermes/tests/test_budget.py:30 |
| 17 | CI installs gitleaks via unauthenticated curl (G6 Step 2 pins checksum) | `curl -fsSL` | .github/workflows/security.yml:58 |
| 18 | G8 executed: verified-planning dev `PLAN.md`/`DESIGN.md` (which enumerated the private monorepo) removed; the skill tool is retained | `verified-planning` | .claude/skills/verified-planning/SKILL.md:2 |
| 19 | G8 executed: the brand/strategy plan (`PLAN-016`) removed; the codename decision survives, redacted, in D-0019 | `D-0019` | plans/DECISIONS.md:217 |

## Review log

> ≥2 passes before implementation; ≥1 independent fresh-context review.

### Pass 1 - 2026-06-14 - author self-review

- Drafted ledger from files opened this session; ran `check_plan.py`, which
  flagged two symbol mismatches (rows 8, 17) — fixed to the literal cited text
  (`1.2.0`, `Bug Report`).
- Corrected an early wrong assumption: `dependabot.yml` is **already present and
  covers both engines** (more complete than the framework's), so it was removed
  from the G2 work list and recorded as a framework-only improvement (F5).

### Pass 2 - 2026-06-14 - independent (general-purpose Agent, fresh context)

Reviewer opened every citation and grepped the repos. All 19 original ledger
rows verified accurate. Findings folded in:

- **[BLOCKING] Active branch ignored.** Task 6 squashed `main` but the repo is on
  `docs/per-repo-governance` (ahead of `main`) and the cleanup list omitted it →
  would drop the latest work. **Fixed:** new Step 1 consolidates *all* wanted
  branches onto `main` before squashing; squash now explicitly orphans from the
  consolidated `main`.
- **[BLOCKING] Submodule re-pin wrong.** Super-repo gitlink is not an ancestor of
  the squashed `main`, so `git submodule update --remote` won't re-point it.
  **Fixed:** Step 4 now sets the gitlink explicitly via checkout + `git add`.
- **[SHOULD] Leak undercount.** G3 missed 5 of 6 path leaks in `PLAN.md`; G4
  missed 3 of 5 sibling refs. **Fixed:** Tasks 4 & 5 now enumerate every line
  (verified by grep); a re-grep gate was added.
- **[SHOULD] Uncited safety claims.** "No `pull_request_target`/`secrets.*`
  across all six workflows" and "history clean" were asserted, not cited.
  **Fixed:** added ledger row 20 + a grep gate in Verification; reworded the
  history claim to name CI `gitleaks` as authoritative (local scan corroborating).
- **[SHOULD] Committed `vladm3105` handle.** **Fixed:** Task 4 Step 2 genericizes
  the internal SSH remote; noted the owner handle itself is acceptably public.
- **[SHOULD] `--force-with-lease` degenerate on orphan** + **[NIT] push-protection
  ordering.** **Fixed:** noted in Step 3 and Step 5.

### Pass 3 - 2026-06-14 - independent (general-purpose Agent, fresh context) - confirmation

Reviewer re-verified against live source: **both blocking fixes confirmed
correct** (branch consolidation orphans from a consolidated `main`; submodule
re-pin is explicit, not `--remote`), leak enumeration **confirmed exhaustive**
(7 path leaks, 5 sibling refs — all listed), and ledger rows 8/17/20 + spot-check
of unchanged rows all resolve. One new finding:

- **[SHOULD] Self-referential G3 gate.** PLAN-018 itself contains `/opt/data/`
  strings (the gate's own search pattern + the `--root` path + leak-location
  docs), so after the squash commits it, the G3 gate would match the plan and
  fail. **Fixed:** the `--root` references now use the relative `../framework`
  form, and the G3 gate (Verification + Task 4 Step 4) now excludes
  `plans/PLAN-018*` with a documented exemption — the plan necessarily contains
  the search pattern and carries no environment leak beyond those self-references.

No other findings. The remaining `/opt/data/` / `/home/` strings in PLAN-018 are
exclusively the gate pattern, the relative-path note, and leak documentation —
all intrinsic to a migration plan and covered by the exemption.

(Passes 1–3 brought the migration mechanics to ready; Pass 4 then deepened the
security review at the maintainer's request.)

### Pass 4 - 2026-06-14 - security review (author, hands-on tree scan)

Because the squash makes the working tree the entire public surface, scanned the
actual bytes to be published. Results recorded in the new `## Security review`
section. No live secrets, credential files, internal-infra refs, or `.claude/`
local config found; baselined items are fake test fixtures. Hardening folded in:

- **Task 6 Step 3 `git add -A` footprint** → added `.gitignore` hardening (Task 4
  Step 5), a dry-run + visual confirm, and an **authoritative post-squash
  `gitleaks detect`** on the squashed artifact (history scan is only
  corroborating, since the squash discards history). New R7, ledger rows 16–17.
- **CI gitleaks binary** unauthenticated download → checksum pin (Task 3 Step 2),
  new R8.
- Documented the committer-email and history-elimination properties.

### Pass 5 - 2026-06-14 - independent (security-auditor Agent, fresh context)

Confirmed safe: no live secrets, baselined items are fixtures, `.claude/` has no
local config/tokens, `git add -A` footprint clean, CI fork-safe, publish ordering
sound (gitleaks gate before push), ledger rows 16–17 accurate, `.gitignore`
hardening necessary.

**[BLOCKING] found — private monorepo + business-strategy disclosure.** The
reviewer caught that the initial scan's `aidoc-flow-` prefix missed *bare*
sibling names. Tracked, to-be-public files (`.claude/skills/verified-planning/
PLAN.md` + `DESIGN.md`, `plans/PLAN-016`, `plans/DECISIONS.md`,
`docs/HANDOFF.md`, `docs/IPLAN-ECOSYSTEM.md`, `CHANGELOG.md`) enumerate the
private repos and internal product/governance strategy (AIOps-Flow,
BRAND_AND_DOMAINS, cross-repo bindings). The Security-review section's "no other
private-sibling refs" claim was false and has been corrected; recorded as **G8**.

**This re-opened the curation decision.** Maintainer chose **curate before
public** (2026-06-14): G8 (Task 5 Steps 3–5) was added to remove the
verified-planning dev artifacts (`PLAN.md`/`DESIGN.md`) + `plans/PLAN-016` and
redact AIOps-Flow/BRAND/cross-repo passages from `DECISIONS.md` + the three docs
+ `PLAN-001`, with a G8 token gate in Verification (R9, ledger rows 18–19).

### Pass 6 - 2026-06-14 - independent (general-purpose Agent, fresh context) - G8 confirmation

Reviewer confirmed G8's removal set is **exhaustive** for the token classes (the
7 token-bearing files all handled; the repo-map loop lives only in the removed
`PLAN.md`), the **kept** verified-planning tool files (`SKILL.md`, `check_plan.py`,
tests, etc.) carry **no** sibling-repo names, and ledger rows 18–19 are accurate.
Two non-blocking findings, both folded in:

- **[SHOULD] Gate under-enforced path-form repo-map.** `DECISIONS.md`/`PLAN-016`
  also disclose the layout as paths (`business/docs/…`, "the `operations` repo")
  that the token gate misses, so a partial redaction could pass green. **Fixed:**
  added a path-form gate `(business|operations)/(docs|ops|src|plans)/` to both the
  G8 gate and Verification, and Step 3 now explicitly calls for removing path-form
  repo refs.
- **[NIT] `IPLAN-ECOSYSTEM.md` misclassified** under G8 (contains no G8 tokens;
  its only sensitive ref is `aidoc-flow-iplanic`, owned by G4). **Fixed:** removed
  from the G8 redaction list with a clarifying note.

Both fixes are mechanically self-verifying via the strengthened gates. No
remaining load-bearing findings.

**Result: ready** — security/disclosure surface curated and gated; the plan is
execution-ready (the publish flip itself remains gated on explicit authorization).
