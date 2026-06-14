# PLAN-016 — codename reassignment (`iops-framework` → AIOps-Flow) + iplan-runner package rename

> Cross-repo governance + refactor plan. Owning repo: **iplan-runner** (the heaviest,
> code-level change). The codename `iops-framework` is **reassigned** from this repo to
> the **AIOps-Flow** AI-team product (in the `operations` repo); iplan-runner drops the
> codename entirely, including its `iops_*` Python packages (renamed `iplan_*`). The
> reassignment **supersedes** the 2026-06 *"4-product family consolidation"* decision
> (`business/docs/DECISIONS.md`) that bound `iops-framework` to iplan-runner; that
> reversal is recorded, not silent. Record as iplan-runner **D-0019** (+ superseding
> entries in `operations/ops/DECISIONS.md` and `business/docs/DECISIONS.md`).

## Decision (D-0019 — supersedes business 2026-06 codename binding)

`iops-framework` is **no longer iplan-runner's codename**. The OSS executor is named
**`iplan-runner`** with **no engineering codename**, and its Python packages drop the
`iops_` brand (`iops_hermes` → `iplan_hermes`, `iops_claude` → `iplan_claude`). The
freed `iops-framework` codename is **reassigned to AIOps-Flow** (the AI-team product
that plans + operates, in `operations/`). This reverses the recorded binding
"iplan-runner (internal codename `iops-framework`)"; `BRAND_AND_DOMAINS.md`
(`business/` + `operations/`) is updated as the source of truth, and the prior
decision entry is marked superseded.

Rationale: the user reassigned the codename; "iops-framework" ("IPLAN-**ops**") is
applied to the AIOps-Flow ops/plan product going forward. iplan-runner is a new OSS
project with no installed base, so dropping `iops_*` (packages + history references)
is clean — no backward-compat shim is needed.

## Scope — by repo

### iplan-runner (this repo — code + docs; one branch/PR)

1. **Package rename** (`iops_hermes` → `iplan_hermes`, `iops_claude` → `iplan_claude`):
   - rename the two source dirs `platforms/hermes/src/iops_hermes/` and
     `platforms/claude/src/iops_claude/` (the `*.egg-info` dirs are **untracked** build
     artifacts — they regenerate; no `git` action);
   - update the **dist name**, **CLI entry-point script name**, and **package-data
     key** in each engine's `pyproject.toml` (`iops-hermes`→`iplan-hermes`,
     `iops-claude`→`iplan-claude`; entry `iops_hermes.cli:main`→`iplan_hermes.cli:main`,
     etc.);
   - **`framework/registry/EXECUTION_REGISTRY.yaml`** (`package: iops_hermes` /
     `iops_claude`, lines 82/85) — the conformance loader `tests/conformance/_spec.py:45`
     does `importlib.import_module(entry["package"])` from this registry, so it **must**
     be renamed in lockstep (see verification note on silent-skip);
   - update **all import sites** — the package token appears on **~182 lines** repo-wide
     (≈115 inside `platforms/**` code + tests; the rest in the registry + docs below),
     not only `platforms/**`;
   - **doc strings** that name the old CLI/package (outside code): `docs/GETTING_STARTED.md`,
     `examples/README.md`, `platforms/hermes/README.md`, `platforms/claude/README.md`,
     `framework/engines/ENGINE-ADAPTER-CONTRACT.md` — so the final grep-clean holds.
2. **Citation cascade** — the gated plans **PLAN-013/014/015** carry Claim-ledger
   citations to `platforms/.../iops_hermes|iops_claude/...` paths; rename breaks them,
   so refresh those citations to the `iplan_*` paths and re-run the gate.
   **PLAN-001..012 are NOT edited.** They predate the Claim-ledger requirement, and the
   CI `plan-gate.yml` gates **every changed `PLAN-*.md` except the template** (it does
   **not** carry the pre-commit `exclude`'s PLAN-001..012 grandfather, `plan-gate.yml:20`),
   so editing a grandfathered plan would make CI run the full gate on it and **fail**
   (no `## Claim ledger`). Their historical `iops_*` references are therefore left as-is
   — the same treatment as the frozen skill rollout docs. (This narrows the user's
   "remove from history" for these specific files; flagged as a necessary governance
   deviation.)
3. **Codename drop (docs):** `README.md` (delete the "internal engineering codename
   `iops-framework` / two names" note), `CLAUDE.md`, `ROADMAP.md`, `CONTRIBUTING.md`,
   `plans/DECISIONS.md` D-0001, and `plans/PLAN-001` goal line (old repo name
   `aidoc-flow-iops-framework` → `iplan-runner`).
4. **Record D-0019** in `plans/DECISIONS.md` (codename dropped + reassigned; supersedes
   the binding); bump `CHANGELOG.md`.
5. **Verify:** per-engine `pytest` + the dual-engine conformance/parity suite green;
   `ruff` + `mypy --strict`; the CLIs (`iplan-hermes`, `iplan-claude`) import and run;
   the plan gate green on PLAN-013/014/015 (refreshed); no `iops_`/`iops-framework`
   token remains except where deliberately historical.

### operations (separate branch/PR) — AIOps-Flow adopts the codename

6. AIOps-Flow **adopts `iops-framework` as its engineering codename** throughout:
   `docs/projects/aiops-flow.md` (charter), `README.md`, `CLAUDE.md`,
   `.claude/agents/aiops-flow-lead.md` (currently points the codename at iplan-runner —
   re-point to AIOps-Flow), `docs/strategy/BRAND_AND_DOMAINS.md`, **and
   `docs/superpowers/plans/2026-05-25-ai-team-autonomous-operations-plan.md`** (lines
   19/240 bind the codename to iplan-runner).
7. **Correct** the `CHANGELOG.md` note that says "`iops-framework` retained as
   engineering codename [for iplan-runner]" → reassigned to AIOps-Flow.
8. Record the reassignment in `ops/DECISIONS.md`.

### business (separate branch/PR) — source of truth

9. `docs/BRAND_AND_DOMAINS.md` is the **source of truth**: rewrite the "internal
   codename `iops-framework`" section + the product table so the codename belongs to
   **AIOps-Flow**, and iplan-runner has **no codename**.
10. Add a **superseding decision** to `docs/DECISIONS.md` (reverses the 2026-06
    "iplan-runner (internal codename `iops-framework`)" binding); update `docs/VISION.md`,
    `docs/TODO.md`, **and `docs/SESSION_HANDOFF.md`** (≈8 refs binding the codename to
    iplan-runner) to match.

### iplanic (separate branch/PR — docs only)

11. Drop the "engineering codename `iops-framework`" clauses (now incorrect) from the
    plans `PLAN-002/003/006/007`, `docs/HANDOFF.md`, and
    `docs/standards/IPLANIC-FIRST-DESIGN.md`; the downstream executor is referred to as
    **`iplan-runner`** (the "IOPS" acronym, where it names this executor, becomes
    `iplan-runner`). Re-run the iplanic gate (the clauses are narrative, not ledger).

**Pre-existing chore branches** (`iplan-runner/chore/rename-old-repo-name-ref`,
`iplanic/chore/rename-iplan-runner-ref`) are **folded into** this plan's branches —
the iplan-runner PLAN-001 chore edit (which added the codename) is re-done here to
**drop** it instead.

## Out of scope

- Renaming the engine identities `hermes` / `claude` (only the `iops_` prefix is
  dropped).
- Any code/behavioral change to the engines, the conformance vectors, or the Iplanic
  wire contract (this is a rename + doc/governance change only — byte-level engine
  behavior is unchanged, proven by the unchanged conformance vectors).
- The `.claude/skills/verified-planning/{PLAN,DESIGN}.md` historical rollout docs in
  any repo (frozen records; their `iops-framework` mentions are a separate, deliberate
  historical reference and the per-repo copies already diverge).
- Rewriting git history (commit messages / past commits) — "remove from history" is
  scoped to current-tree references, not a history rewrite.

## Tasks

1. **iplan-runner — rename packages.** `git mv` the two `iops_*` source dirs to
   `iplan_*`; replace `iops_hermes`→`iplan_hermes`, `iops_claude`→`iplan_claude`
   repo-wide — `platforms/**` (code + tests + `pyproject.toml` name/entry/package-data),
   **`framework/registry/EXECUTION_REGISTRY.yaml`** (the conformance loader's import
   source), and the doc strings (`docs/GETTING_STARTED.md`, `examples/README.md`, both
   engine `README.md`, `framework/engines/ENGINE-ADAPTER-CONTRACT.md`). Re-run each
   engine's `pytest`, the conformance/parity suite, `ruff`, `mypy --strict`; smoke the
   renamed CLIs.
2. **iplan-runner — refresh plan citations.** Update `iops_*` path citations in
   **PLAN-013/014/015 only** (gated; have Claim ledgers) to `iplan_*`; re-run the gate
   on them. **Do not touch PLAN-001..012** — the CI `plan-gate.yml` would gate any
   changed PLAN file and they lack ledgers, so editing them fails CI; their historical
   `iops_*` refs stay.
3. **iplan-runner — drop codename docs + decision.** Edit README/CLAUDE/ROADMAP/
   CONTRIBUTING/DECISIONS-D-0001/PLAN-001; add **D-0019**; CHANGELOG. Gate + pre-commit
   green; commit on `plan/iplan-016-codename-reassign`.
4. **operations — adopt codename.** Edit aiops-flow.md/README/CLAUDE/aiops-flow-lead/
   BRAND_AND_DOMAINS; correct CHANGELOG; add `ops/DECISIONS.md` entry. Commit on its own
   branch.
5. **business — source of truth.** Rewrite BRAND_AND_DOMAINS codename ownership; add the
   superseding `DECISIONS.md` entry; update VISION/TODO. Commit on its own branch.
6. **iplanic — drop codename clauses.** Edit PLAN-002/003/006/007 + HANDOFF +
   IPLANIC-FIRST-DESIGN (executor → `iplan-runner`); re-run the gate. Commit on its own
   branch.
7. **Report** the four branches for the user to merge (never merge without command).

## Verification

- iplan-runner: per-engine `pytest` + dual-engine conformance/parity green — **and the
  conformance suite must report a non-zero engine count**, because
  `tests/conformance/_spec.py:41` *silently skips* engines it cannot import, so a missed
  `EXECUTION_REGISTRY.yaml` rename would make the suite pass green against **zero**
  engines (a false pass). `ruff` + `mypy --strict` clean; `iplan-hermes`/`iplan-claude`
  CLIs run; plan gate green on the refreshed PLAN-013/014/015;
  `grep -rn "iops_hermes\|iops_claude\|iops-framework"` returns nothing **except** the
  grandfathered PLAN-001..012 and the historical `.claude/skills/verified-planning`
  rollout docs (both deliberately out of scope).
- operations/business/iplanic: their gates/pre-commit (where present) green; no
  remaining "iplan-runner (codename iops-framework)" binding; AIOps-Flow now carries
  the codename in BRAND_AND_DOMAINS (both copies agree).
- Governance: the 2026-06 business decision is marked **superseded** by a new dated
  entry; iplan-runner D-0019 + operations `ops/DECISIONS.md` entry record the
  reassignment.

## Claim ledger

> Every load-bearing claim cites the `file:line` actually read. All in-repo (iplan-runner);
> cross-repo edits (operations/business/iplanic) are described as tasks, not cited rows.

| #   | Claim | Symbol | Citation |
| --- | ----- | ------ | -------- |
| 1   | the hermes engine import package is `iops_hermes` (a source dir to rename) | `task_completed` | platforms/hermes/src/iops_hermes/orchestrator/loop.py:223 |
| 2   | the hermes engine **dist name** is `iops-hermes` (to rename) | `name = "iops-hermes"` | platforms/hermes/pyproject.toml:6 |
| 3   | the hermes **CLI entry point** binds the `iops_hermes.cli:main` callable | `iops_hermes.cli:main` | platforms/hermes/pyproject.toml:23 |
| 4   | the hermes **package-data** is keyed on `iops_hermes` | `iops_hermes` | platforms/hermes/pyproject.toml:29 |
| 5   | the claude engine **dist name** is `iops-claude` (to rename) | `name = "iops-claude"` | platforms/claude/pyproject.toml:6 |
| 6   | the claude **CLI entry point** binds `iops_claude.cli:main` | `iops_claude.cli:main` | platforms/claude/pyproject.toml:21 |
| 7   | the claude **package-data** is keyed on `iops_claude` | `iops_claude` | platforms/claude/pyproject.toml:27 |
| 8   | import sites use `from iops_hermes...` (one of ~167 reference lines) | `from iops_hermes.budget` | platforms/hermes/tests/test_budget.py:9 |
| 9   | the README binds `iops-framework` as iplan-runner's codename (to delete) | `iops-framework` | README.md:7 |
| 10  | CLAUDE.md states the `iops-framework` codename | `iops-framework` | CLAUDE.md:3 |
| 11  | ROADMAP.md states the `iops-framework` codename | `iops-framework` | ROADMAP.md:5 |
| 12  | CONTRIBUTING.md states the `iops-framework` codename | `iops-framework` | CONTRIBUTING.md:4 |
| 13  | PLAN-001's goal still uses the old repo name `aidoc-flow-iops-framework` | `aidoc-flow-iops-framework` | plans/PLAN-001_iplan-execution-ledger-runtime.md:8 |
| 14  | DECISIONS D-0001 binds the codename to iplan-runner (to amend) | `engineering codename` | plans/DECISIONS.md:10 |
| 15  | the **pre-commit** hook grandfathers PLAN-001..012; PLAN-013+ are gated locally | `grandfather PLAN-001..012` | .pre-commit-config.yaml:62 |
| 16  | gated PLAN-013 carries an `iops_hermes` path citation (cascade on rename) | `task_completed` | plans/PLAN-013_iplanic-remote-executor-conformance.md:433 |
| 17  | gated PLAN-015 carries `iops_hermes` path citations (cascade on rename) | `_REQUIRED_IDS` | plans/PLAN-015_iplanic-repin-executor-id.md:153 |
| 18  | the conformance engine **registry** binds each engine to its import package `iops_hermes`/`iops_claude` (must rename in lockstep) | `package: iops_hermes` | framework/registry/EXECUTION_REGISTRY.yaml:82 |
| 19  | the conformance loader **imports** engines by the registry `package` and **silently skips** unimportable ones (a missed registry rename = green-against-zero-engines) | `import_module` | tests/conformance/_spec.py:45 |
| 20  | the **CI** `plan-gate.yml` gates **every** changed `PLAN-*.md` except the template — it does **not** carry the pre-commit PLAN-001..012 grandfather, so editing 001..012 fails CI | `PLAN-TEMPLATE` | .github/workflows/plan-gate.yml:20 |

## Review log

> ≥2 passes before ready. ≥1 independent fresh-context (`Agent`). Final pass states
> zero findings.

### Pass 1 - 2026-06-14 - author

- Verified all 17 ledger citations by opening each file at the cited line.
- Confirmed the change is **rename + governance**, not behavioral: the engines, the
  conformance vectors, and the Iplanic wire contract are untouched; only the `iops_`
  package prefix and the `iops-framework` codename move.
- Confirmed the **citation cascade**: PLAN-013/014/015 are gated and cite `iops_*`
  paths, so the package rename forces a ledger refresh + gate re-run (Task 2).
- Confirmed the **governance conflict** is real and must be recorded: `business/docs/
  DECISIONS.md` (2026-06) + `BRAND_AND_DOMAINS.md` bind `iops-framework` to iplan-runner
  and reassign the *name* "AIOps-Flow" to the AI-team product; this plan reverses the
  codename binding, so it adds a superseding decision rather than editing silently.
- Open questions for the independent pass: (a) does the engine **dist-name**/entry-point
  rename (`iops-hermes`→`iplan-hermes`) have any consumer (CI, docs, another repo) that
  pins the old script name? (b) are there `iops_` references **outside `platforms/**`**
  (e.g. root `pyproject`, `tests/` conformance harness, CI workflows) the 167-count
  might miss? (c) does any **operations/business** doc bind the codename to iplan-runner
  in a spot not yet enumerated (so the reassignment is incomplete)?

### Pass 2 - 2026-06-14 - independent

Fresh-context reviewer verified **all 17 original citations accurate** (opened each
`file:line`; symbols within ±3 lines) and answered the three open questions against the
real tree. Found **5 load-bearing gaps** — all folded in (ledger rows 18-20 added):

- **(L1) The conformance engine registry was out of scope.**
  `framework/registry/EXECUTION_REGISTRY.yaml:82/85` (`package: iops_hermes`/
  `iops_claude`) is read by `tests/conformance/_spec.py:45`
  (`importlib.import_module(entry["package"])`); a missed rename breaks engine import.
  Worse, `_spec.py:41` **silently skips** unimportable engines → the suite can pass
  **green against zero engines**. → added to Scope §1 + Task 1 + ledger rows 18-19, and
  Verification now requires a **non-zero engine count**.
- **(L2) CI `plan-gate.yml` does not grandfather PLAN-001..012.** Only the *pre-commit*
  `exclude` does (`.pre-commit-config.yaml:62`); `plan-gate.yml:20` filters out only the
  template, so editing the ledger-less PLAN-001..012 would **fail CI**. → Task 2 + Scope
  §2 corrected: refresh **PLAN-013/014/015 only**; leave 001..012 historical (ledger row
  20). This narrows the user's "remove from history" for those files (necessary
  governance deviation, flagged for approval).
- **(L3) Package token undercounted + outside `platforms/**`.** ~182 lines repo-wide,
  not "~167 across platforms/**"; the miss set includes the registry (L1) and doc strings
  (`docs/GETTING_STARTED.md`, `examples/README.md`, both engine `README.md`,
  `framework/engines/ENGINE-ADAPTER-CONTRACT.md`). → Scope §1 + Task 1 widened so the
  final grep-clean verification holds.
- **(L4) Unenumerated cross-repo codename bindings.** operations
  `docs/superpowers/plans/2026-05-25-ai-team-autonomous-operations-plan.md:19/240` and
  business `docs/SESSION_HANDOFF.md` (≈8 refs) bind the codename to iplan-runner but
  were absent from Tasks 4/5. → both added.
- **(L5) `*.egg-info`** is untracked (not `git`-tracked), so "drop the stale artifacts"
  was a no-op for the repo. → Scope §1 corrected (MINOR).

Reviewer confirmed sound: next decision number is **D-0019** (highest heading D-0018);
CI installs engines by **path** not dist-name (rename is CI-safe); the import-isolation
test keys off the registry, not hardcoded strings (safe once the registry is renamed);
the citation cascade is real and `check_plan.py` enforces it.

**No remaining load-bearing findings.**

**Result:** ready — no further findings.
