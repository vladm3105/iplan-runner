# PLAN-023 — Consume the IPLAN standard (replace the stale fork)

> **Goal:** make iplan-runner a **real, pinned consumer** of the now-public
> [`iplan-standard`](https://github.com/vladm3105/aidoc-flow-iplan-standard) (`iplan/v0.1.0`) instead of a
> stale hand-copied fork. Today iplan-runner consumes the standard three ways, all hand-rolled and drifting:
> (1) a **vendored schema mirror** (`framework/remote/*.yaml`) pinned to an old iplanic commit `fb5f46d` —
> **stale** (`repository: "."` vs the live object, the PLAN-021 bug); (2) a vendored contract doc; (3) a
> **parallel reimplementation** of the canonical-JSON + signing (`security/iplanic_signing.py`, per engine).
> The mirror's promise that "drift surfaces as a failing conformance vector" **does not fire** — the
> canonicalization vectors don't cover the payload *shape*, so the `repository: "."` drift slipped through
> silently (the PLAN-021 bug). (The vectors themselves are in fact still in sync with the tag; the real drift
> is the YAML mirror + the un-pinned provenance.) This slice: **re-derive the mirror** to the current shape,
> **re-pin** the provenance + vectors, **unify signing onto a vendored copy of the standard's `iplan_canonical`
> (behind the existing shim name)**, and add a **drift-check that byte-diffs the byte-copyable surface** —
> turning silent drift into an impossible state.
>
> **Founder-executed / cross-repo:** *prepared* by the AI (read-only); the founder reviews, implements, and
> runs all git operations. Rows marked `[std]` resolve with `check_plan --root /opt/data/aidoc-flow/iplan-standard`.
>
> **Strict engine isolation (D-0011):** done in **both** `platforms/claude` and `platforms/hermes`, no shared
> code (the vendored standard surface is a per-engine self-contained copy).

## Architecture

```
iplan-standard @ iplan/v0.1.0  (source of truth: schemas/, iplan_canonical/, canonicalization vectors)
        │  (vendor-pin, drift-checked against the tag — NOT a stale hand-copy)
        ▼
iplan-runner:
  framework/remote/*.yaml        ← re-synced from schemas/ (fixes repository-object drift)
  framework/remote/iplanic-vectors/  ← re-synced from tests/contract/canonicalization/vectors/
  platforms/<engine>/.../security/iplan_canonical.py  ← verbatim copy of iplan-standard's iplan_canonical
        (replaces the DIVERGENT iplanic_signing.py; same RFC 8785 + ed25519/hmac algorithm)
  sync/check-drift.sh            ← NEW: fetch the tag, diff the vendored surface, fail on drift
```

## Scope

**In (both engines):**

1. **Re-derive the schema mirror** — the `framework/remote/*.yaml` are **hand-authored consumed-subset
   *instances*** (e.g. `IPLAN-TASK-PAYLOAD-TEMPLATE.yaml` is a filled example with only the fields the
   executor reads), **not** the schema verbatim — so this is a **re-derivation/transform** from
   `iplan-standard@iplan/v0.1.0`'s `schemas/task.schema.json` + `execution-event.schema.json`, **not a
   byte-copy**. Re-author the subset to the current shape — chiefly **`repository` object** `{url,
   default_branch, base_ref}` (fixing the `repository: "."` drift) — and re-pin the provenance header (source
   = `iplan-standard`, tag `iplan/v0.1.0`, not `fb5f46d`/`1.3-draft`). Correctness is verified by validating
   the example against the tag's schema (or via PLAN-021's adapter test), **not** by a byte-diff (the YAML
   subset is not byte-comparable to a JSON Schema — see the drift-check scope below).
2. **Unify the canonicalization/signing** — **vendor the standard's `iplan_canonical` as a package**
   (`security/iplan_canonical/{__init__,canonical,signing}.py`, a *verbatim* copy of the tag — `signing.py`
   does `from .canonical import …`, so it must be the directory, not a single file), and make the existing
   `security/iplanic_signing.py` a **thin re-export shim** over it (`from .iplan_canonical.signing import
   sign, verify, signing_payload`; `from .iplan_canonical.canonical import canonicalize, drop_null,
   canonical_hash`). This **preserves the public name + API**, so the importers (`ledger/events.py:15`), the
   `security/__init__.py` `__all__`, and the conformance test `tests/conformance/test_iplanic_signing.py`
   (which imports `…security.iplanic_signing` by path) are **unchanged** — no rename blast radius. The two
   only become byte-identical to iplanic by construction (one vendored source); the standard's copy is a
   **superset** (adds `evidence_seal_hash`, `CANONICALIZATION_VERSION`) — additive, harmless. **Two
   `mypy --strict` accommodations** (`ci.yml:76` runs strict over `src/`): (a) the vendored package is
   **untyped** (the standard's `iplan_canonical` has no annotations) — add a scoped
   `[[tool.mypy.overrides]] module = "iplan_<engine>.security.iplan_canonical.*"` with
   `disallow_untyped_defs = false` (keeps the copy *verbatim* — byte-identity — while strict still covers the
   rest); (b) the shim must declare an explicit **`__all__`** (or `import x as x`) so
   `no_implicit_reexport` accepts re-exporting `sign`/`signing_payload`/`canonicalize`/… through
   `iplanic_signing`.
3. **Re-pin the conformance vectors** — the `framework/remote/iplanic-vectors/canon_*.json` + `sig_*.json` +
   `seal_hash.json` + `normalize_omit_vs_null.json` are **already byte-identical** to the tag's
   `tests/contract/canonicalization/vectors/` (verified) — so this is just bumping `SOURCE.md`'s provenance
   to `iplan/v0.1.0` (the real drift is the YAML mirror + the signing copy, not the vectors).
4. **A real drift-check** — add `sync/check-drift.sh` (pre-commit hook / periodic Action) that fetches
   `iplan-standard@iplan/v0.1.0` and **byte-diffs only the byte-copyable surface** — the vendored
   `security/iplan_canonical/` package + the `iplanic-vectors/` `*.json` (tracked content only; exclude
   `__pycache__` **and the runner-local `SOURCE.md`**, which has no counterpart in the tag) — **failing on
   drift**. The **YAML mirror is excluded** from the byte-diff (it's a derived subset, not byte-comparable);
   its conformance is the re-derivation + the **PLAN-021 adapter test** (the primary check — iplan-runner has
   no `jsonschema`, so schema-validation of the mirror is via that path, not a JSON-Schema validator). This
   replaces the non-functional "drift surfaces as a failing vector" claim with a check that actually compares
   comparable artifacts.

**Out (deferred):**

- **Consuming the prose specs** (`IPLAN-ECOSYSTEM` / `TRANSPORT-INTEGRATION` / `PLAN-INGESTION-ADAPTERS`) — held
  in iplan-standard until `iplan/v0.2.0`; the vendored `REMOTE_EXECUTOR_CONTRACT.md` stays iplan-runner's own
  contract doc for now.
- **A pip/git package dependency** on `iplan-canonical` — vendoring keeps the OSS install self-contained (no
  network dep); revisit if/when the standard publishes to an index.
- No change to the executor/orchestrator runtime behavior.

## Approach

iplan-runner already has the right *idea* (vendor a pinned mirror, drift-check it) — it just never wired a
working pin or a working check, so it forked silently (the PLAN-021 bug). This slice keeps the vendor model
(self-contained, OSS-friendly) but makes the pin **real**: re-sync every vendored artifact from the *tagged*
standard, and replace the hand-wave drift claim with a script that byte-diffs the byte-copyable surface. The
signing is the one *code* change: the parallel `iplanic_signing.py` is the highest drift risk (a divergent
canonical hash silently breaks iplanic's signature verification), so the standard's `iplan_canonical` is
vendored verbatim **as a package** and `iplanic_signing.py` becomes a **thin re-export shim** over it — the
public name + API are preserved, so no importer, `__all__`, or conformance test changes (zero rename blast
radius), and the hashes/signatures become byte-identical to iplanic by construction. The YAML mirror is the
subtle part: it is a hand-derived *subset instance*, not the schema, so it is **re-derived** (a transform,
not a copy) and its correctness is a schema-validation / the PLAN-021 adapter test — it is deliberately
**excluded from the byte-diff** (a YAML subset isn't byte-comparable to a JSON Schema). Per-engine isolation
is preserved: each engine carries its own vendored copy; nothing is shared between engines.

## File structure

- `framework/remote/{IPLAN-TASK-PAYLOAD-TEMPLATE,EXECUTION-EVENT-TEMPLATE}.yaml` + `REMOTE_EXECUTOR_CONTRACT.md`
  — **re-derived** subset + re-pinned provenance.
- `framework/remote/iplanic-vectors/SOURCE.md` — provenance re-pinned (the vector files are already in sync).
- `platforms/<engine>/src/iplan_<engine>/security/iplan_canonical/{__init__,canonical,signing}.py` — **new
  vendored package** (verbatim copy of the tag); `security/iplanic_signing.py` becomes a **thin re-export
  shim** over it (public name + API preserved → importers / `__all__` / `tests/conformance/test_iplanic_signing.py`
  unchanged).
- `sync/check-drift.sh` — the tag drift-check (scoped to `security/iplan_canonical/` + `iplanic-vectors/`).

## Step sequence

1. **Re-derive + re-pin** the YAML mirror to the current shape (`repository` object) + re-pin the provenance
   headers; re-pin `iplanic-vectors/SOURCE.md`.
2. **Vendor `iplan_canonical` as a package** per engine; make `iplanic_signing.py` a thin re-export shim
   (public name + API preserved). Run the conformance suite — `test_iplanic_signing.py` + the
   canonicalization/signature vectors must pass **unchanged** (proving byte-identity + zero blast radius).
3. **`sync/check-drift.sh`** (byte-diff `security/iplan_canonical/` + the vectors vs the tag) + wire it
   (pre-commit / Action). Run it (expect: in-sync, exit 0).
4. **Slim PLAN-021** to depend on this (drop its "re-pin the stale mirror" step — the receiver now validates
   against the re-derived schema).
5. Docs of record (`plans/HANDOFF.md`, `plans/DECISIONS.md` D-0023, `CHANGELOG.md`).

## Verification

- `pytest platforms/hermes platforms/claude -q` + `python -m unittest discover -s tests/conformance -v` green
  **unchanged** — the shim preserves `security.iplanic_signing`, so `test_iplanic_signing.py` + the
  canonicalization/signature vectors pass without edits (the byte-identity + zero-blast-radius gate).
- `sync/check-drift.sh` exits 0 against `iplan/v0.1.0` (the vendored `iplan_canonical/` package + vectors match
  the tag, tracked-content-only).
- A targeted assertion: the re-derived `IPLAN-TASK-PAYLOAD-TEMPLATE.yaml` carries `repository` as the
  **object** shape (the drift is fixed) — verified via **PLAN-021's adapter test** (the primary path; no
  `jsonschema` dep); confirm no `repository: "."`.
- `ruff` + pre-commit clean; **`mypy --strict` clean** — with the scoped override for the untyped vendored
  `security/iplan_canonical/*` + the shim's explicit `__all__` (so `no_implicit_reexport` accepts the
  re-exports); strict still covers all non-vendored code.

## Risks

| # | Risk | Mitigation |
| --- | --- | --- |
| 1 | The signing swap changes a hash/signature (breaks iplanic verification) | Vendored verbatim + a shim that re-exports the same public API; the unchanged `test_iplanic_signing.py` + canonicalization/signature vectors are the byte-identity gate (Step 2). |
| 2 | The re-derived mirror diverges from what intake expects | The mirror is the *consumed subset*; re-derived to the current `repository`-object shape; PLAN-021's `adapt_dispatched_task` bridges object→workspace; validated against the tag's schema. |
| 3 | The drift-check is flaky (network to fetch the tag) | `sync/check-drift.sh` is opt-in (pre-commit / periodic Action), not a per-PR hard gate; fetches a pinned immutable tag; compares **tracked content only** (exclude `__pycache__`). |
| 4 | Engine drift claude/hermes | Both engines vendored from the same tag; the conformance replay asserts cross-engine parity. |
| 5 | The YAML mirror can't be byte-diffed against the tag (it's a subset instance, not the JSON Schema) | The byte-diff is **scoped** to `iplan_canonical/` + the vectors (true byte-copies); the mirror is re-derived + schema-validated, not byte-diffed. |
| 6 | Renaming the signing module would break importers / `__all__` / `test_iplanic_signing.py` | **No rename** — the shim keeps `security.iplanic_signing`; the vendored copy lives at `security/iplan_canonical/`; zero importer/test changes. |
| 7 | The verbatim (untyped) vendored package fails `mypy --strict` (`ci.yml:76` recurses `src/`) | A scoped `[[tool.mypy.overrides]]` (`disallow_untyped_defs = false`) for `…security.iplan_canonical.*` keeps the copy verbatim while strict covers the rest. |
| 8 | `mypy --strict` `no_implicit_reexport` rejects the shim's re-exports | The shim declares an explicit `__all__` (or `import x as x`). |
| 9 | The drift-check flags the runner-local `SOURCE.md` (no tag counterpart) | Compare `*.json` only; exclude `SOURCE.md` + `__pycache__`. |

## Proposed decision — D-0023

**(consume the IPLAN standard)** Make iplan-runner a pinned consumer of `iplan-standard@iplan/v0.1.0`:
**re-derive** the `framework/remote/` YAML subset to the current shape (fixing the `repository`-object drift)
+ re-pin provenance; **vendor the standard's `iplan_canonical` as a package** and turn `iplanic_signing.py`
into a thin re-export shim (public name + API preserved → byte-identical hashes/signatures, zero importer/
test blast radius); re-pin the (already-in-sync) vectors' provenance; add `sync/check-drift.sh` that
**byte-diffs the byte-copyable surface** (the vendored package + vectors, tracked-content-only) and fails on
drift — the YAML subset is schema-validated, not byte-diffed. Vendor-pin (not a git dependency) to keep the
OSS install self-contained. **Deferred:** the held prose specs (v0.2.0); a package dependency. **Why:**
iplan-runner consumed the standard by stale hand-copies with a non-functional drift claim, which silently
forked (the PLAN-021 bug); a real, scoped drift-check + one shared canonicalization source (behind the
existing shim) makes drift structurally impossible without a rename.

## Claim ledger

iplan-runner paths relative to `/opt/data/aidoc-flow/iplan-runner` (post-implementation: the standard is
vendored in-repo, so the ledger is self-contained — no `--root` needed). Engines identical per seam; the
claude path is cited.

| # | Claim | Symbol | Citation |
| --- | --- | --- | --- |
| 1 | the mirror is re-pinned to `iplan/v0.1.0` (was the old iplanic commit `fb5f46d`) | `pinned tag:` | framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml:5 |
| 2 | the mirror now carries `repository` as the object (the `repository: "."` drift fixed) | `repository:` | framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml:32 |
| 3 | the mirror is a hand-derived subset, re-derived from the tag (the non-functional drift-claim removed) | `hand-derived SUBSET (an instance)` | framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml:10 |
| 4 | the contract doc is re-pinned to `iplan-standard@iplan/v0.1.0` (from `1.3-draft`/`fb5f46d`) | `iplan-standard@iplan/v0.1.0` | framework/remote/REMOTE_EXECUTOR_CONTRACT.md:15 |
| 5 | the canonicalization/signing the shim re-exports — vendored verbatim from the standard (was the divergent `iplanic_signing.py`) | `SIGNATURE_ALGORITHMS = ("hmac-sha256", "ed25519")` | platforms/claude/src/iplan_claude/security/iplan_canonical/signing.py:22 |
| 6 | `canonicalize` (the RFC 8785 core, now in the vendored package) | `def canonicalize` | platforms/claude/src/iplan_claude/security/iplan_canonical/canonical.py:24 |
| 7 | `ledger/events.py` imports the signing (one of the ~5 import sites to swap) | `from ..security.iplanic_signing import` | platforms/claude/src/iplan_claude/ledger/events.py:15 |
| 8 | the vendored canonicalization vectors live here (provenance re-pinned; files already in sync) | `Vendored Iplanic conformance vectors` | framework/remote/iplanic-vectors/SOURCE.md:1 |
| 8b | the conformance test imports `security.iplanic_signing` **by module path** — the shim preserves it (no edit) | `import_module(f"{entry['package']}.security.iplanic_signing")` | tests/conformance/test_iplanic_signing.py:30 |
| 8c | `security/__init__.py` re-exports `iplanic_signing` in `__all__` — the shim preserves the public name | `"iplanic_signing"` | platforms/claude/src/iplan_claude/security/__init__.py:8 |
| 8d | CI runs `mypy --strict` over `src/` (recurses the vendored dir) → the scoped override + shim `__all__` are required | `mypy --strict platforms/hermes/src platforms/claude/src` | .github/workflows/ci.yml:76 |
| 9 | the consumed `repository` is re-derived to the object shape from the tag (`url`/`default_branch`/`base_ref`) | `url:` | framework/remote/IPLAN-TASK-PAYLOAD-TEMPLATE.yaml:33 |
| 10 | the vendored `iplan_canonical` (verbatim from the tag) the shim re-exports | `SIGNATURE_ALGORITHMS` | platforms/claude/src/iplan_claude/security/iplan_canonical/signing.py:22 |
| 11 | the vendored canonicalization golden vectors (byte-identical to the tag; drift-checked) | `"org_id"` | framework/remote/iplanic-vectors/canon_event.json:3 |

## Review log

(to be filled — ≥2 passes, ≥1 independent fresh-context Agent; final pass states zero load-bearing findings.
Cross-repo gate: `check_plan --root /opt/data/aidoc-flow/iplan-standard`.)

### Pass 1 - 2026-06-23 - author self-review

Re-read every cited line across both repos. The mirror is stale-pinned to `fb5f46d`/`1.3-draft`
(`IPLAN-TASK-PAYLOAD-TEMPLATE.yaml:6`/`REMOTE_EXECUTOR_CONTRACT.md:15`) with `repository: "."` (`:31`) and a
non-functional drift claim (`:11`); the standard's `task.schema.json:171` `[std]` is the object-shape
re-sync target. The signing copy (`iplanic_signing.py:31`/`:44`, imported at `ledger/events.py:15`) shares
the standard's `SIGNATURE_ALGORITHMS` (`iplan_canonical/signing.py:22` `[std]`), so the swap is an
import-path change; the vectors (`iplanic-vectors/SOURCE.md`, std `canon_event.json:3`) prove byte-identity.
Vendor-pin (not a git dep) keeps the OSS install self-contained; the drift-check makes the pin real. Both
engines mirrored.

Ready for independent review.

### Pass 2 - 2026-06-23 - independent (general-purpose Agent, fresh context)

A fresh-context Agent verified all 11 citations resolve + the tag is real, and returned **5 load-bearing
findings in the plan mechanics** (not the ledger) — all folded:

1. **Wrong import-site list** — the only real importers are `ledger/events.py:15` + `security/__init__.py`
   (the named `relay/`, `engine.py`, `orchestrator/control.py` import `security.signing`/`authz`, *not*
   `iplanic_signing`). **Resolved by the shim** (no importer changes at all).
2. **The YAML mirror can't be byte-diffed** — it's a hand-derived consumed-subset *instance*, not the JSON
   Schema. Re-sync is a **re-derivation/transform**, and the drift-check is **scoped** to the byte-copyable
   surface (the vendored `iplan_canonical/` + vectors); the mirror is schema-validated, not byte-diffed
   (Scope 1/4, Approach, Risk #5).
3. **Single-file vendoring infeasible** — `iplan_canonical` is a package (`signing.py` does `from .canonical
   import`). **Vendor the directory** `security/iplan_canonical/` (Scope 2, File structure).
4. **Rename would break the conformance test + `__all__`** (`test_iplanic_signing.py:30` imports by path;
   `security/__init__.py:8`). **Resolved by NOT renaming** — `iplanic_signing.py` becomes a thin re-export
   shim over the vendored package; importers/`__all__`/test unchanged (Scope 2, Risk #6, rows 8b/8c).
5. **API is one-directional** (the standard's `iplan_canonical` is a *superset* — adds `evidence_seal_hash`,
   `CANONICALIZATION_VERSION`) — additive/harmless; the shim re-exports the names the runner uses (Scope 2).

MINOR folded: the **vectors are already in sync** (the "vectors stale" premise was wrong — the real drift is
the YAML mirror + provenance); the byte-diff compares **tracked content only** (exclude `__pycache__`).

### Pass 3 - 2026-06-23 - independent re-review (general-purpose Agent, fresh context)

A fresh-context Agent confirmed the 5 prior fixes are coherent + complete (the shim is sound — the standard's
`iplan_canonical/__init__.py` re-exports every name the runner uses, and the runner's extra constants
`SIGNATURE_ALGORITHMS`/`HASH_ALGORITHM`/… are referenced nowhere outside the module, so the shim needn't
re-export them; the 9 vectors are byte-identical to the tag; all 13 citations resolve). **2 new load-bearing
findings — both the `mypy --strict` CI gate (`ci.yml:76`), folded:**

- The verbatim **untyped** vendored package fails `disallow_untyped_defs` → a scoped `[[tool.mypy.overrides]]`
  for `…security.iplan_canonical.*` (keeps the copy verbatim; strict covers the rest) (Scope 2, Risk #7,
  Verification, ledger row 8d).
- `no_implicit_reexport` rejects the shim's re-exports → the shim declares an explicit `__all__` (Scope 2,
  Risk #8).

MINOR folded: the drift-check compares `*.json` only + excludes the runner-local `SOURCE.md` (Risk #9); the
mirror's schema-validation is the **PLAN-021 adapter test** (no `jsonschema` dep) (Scope 1, Verification).

- **Verdict: ZERO load-bearing findings.**

**Result:** ready (founder-executed). iplan-runner consumes `iplan-standard@iplan/v0.1.0`: re-derive the YAML
subset (fix the `repository`-object drift) + re-pin provenance; vendor the standard's `iplan_canonical` as a
package with `iplanic_signing.py` as a thin re-export shim (zero rename blast radius; `mypy --strict` handled
via a scoped override + `__all__`); a scoped, tracked-content drift-check (`iplan_canonical/` + vector
`*.json`); the mirror validated via the PLAN-021 adapter test. **Depends on `iplan/v0.1.0` (live); pairs with
PLAN-021 (slim its mirror-repin step).**

### Implementation note - 2026-06-23

Executed (per founder instruction). One refinement to the `mypy --strict` accommodation: instead of the
planned scoped `[[tool.mypy.overrides]]` (`disallow_untyped_defs=false`), the implementation adds runner-local
**`.pyi` type stubs** beside the verbatim untyped vendored modules (`security/iplan_canonical/{canonical,
signing}.pyi`). The override could not fix the *caller-side* `no-untyped-call` (e.g. `ledger/events.py`
calling the untyped `sign`); the stubs give mypy a typed interface for both the module and its callers while
keeping the `.py` byte-identical to the tag (stubs are not `*.py`, so the drift-check ignores them; runtime
loads the verbatim `.py`). The shim's explicit `__all__` (for `no_implicit_reexport`) is unchanged. Verified:
conformance 26 + 244 offline tests green, `sync/check-drift.sh` in-sync + a negative test, ruff clean, zero
new mypy errors.
