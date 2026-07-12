# PLAN-025 — Pre-prod hardening (receiver security, wire contract, lifecycle)

**Status:** draft → ready-for-build pending independent review
**Created:** 2026-07-09
**Owner repo:** iplan-runner (public OSS, MIT; two engines: `platforms/claude`,
`platforms/hermes`)
**Wave:** 1 — B1/B3/lifecycle items are independent and can start immediately;
the S4 re-pin depends on **iplan-standard PLAN-0001** cutting `iplan/v0.5.0`.

> **Engine parity:** `vcs/`, `relay/`, `budget.py`, `validation/`, and most of
> `receiver/` are byte-identical across the two engines (verified). **Exception
> (independent review):** `receiver/service.py` differs by 3 lines
> (`HermesEngine`↔`ClaudeEngine` type names) — a mechanical parity-diff in CI must
> exclude the engine-name lines or it flags `service.py` forever. Every code fix
> below MUST be applied to **both** `platforms/claude/src/iplan_claude/…` and
> `platforms/hermes/src/iplan_hermes/…` and kept in lockstep. Citations use the
> `hermes` path; the `claude` twin is identical except for those engine-name lines.

## Why this exists

Pre-prod review found one remote-code-execution path, one live wire-contract bug
that breaks retry/halt semantics against iplanic, and several
lifecycle/robustness gaps (no timeout enforcement, no cleanup/retention, no
crash recovery). This is a public repo, so any "trusted caller" assumption is a
finding.

## Scope — findings → fixes

### P1 (BLOCKER — security + wire correctness)

| ID | Finding | Fix |
| --- | --- | --- |
| B1 | **RCE via clone URL.** `clone()` runs `git clone … <url>` with `url` straight from the dispatch payload; `validate_payload` only checks it is a non-empty string. `url="ext::sh -c <cmd>"` triggers git's `ext::` remote-helper → arbitrary shell on the runner host; `file://` also accepted. A leading-`-` `url`/`ref` is also an argument-injection vector. | In `validation/payload_rules.py` add a scheme allow-list for `context_package.repository.url` — permit only `https://` (and `git+ssh://`/`ssh://` if intended); reject `ext::`, `file://`, `-`-leading, and any scheme not on the list, as a hard validation `Finding`. In `vcs/git.py` harden argv against leading-dash values: put `--` **after** the URL in `clone` (`git clone --no-single-branch -- <url> <dest>`) and use a **trailing** `--` on checkout (`git checkout <ref> --`) or rev-parse-then-checkout-SHA. **⚠ correction (independent review):** do NOT put `--` *before* `<ref>` — `git checkout -- <ref>` treats `<ref>` as a **pathspec**, not a rev, breaking every branch/tag/SHA checkout (and `test_vcs.py` clone tests). **Required test change (independent review):** the B1 scheme allow-list rejects the `file://` URLs that existing receiver fixtures build via `src.as_uri()` (`test_task_receiver.py`, `test_receiver_workspace.py`, `test_receiver_executor_wiring.py`) — add a **test-only scheme exemption** (env flag) or switch those fixtures to a served `https`/`git` URL, alongside the new rejection tests (`ext::`, `file://`, leading-`-`). |
| B3 | **Reject-envelope field mismatch.** `classify()` reads `response.body["reject_code"] or ["code"]`, but iplanic only ever emits `{"reason": …}`. Result: `timestamp_skew` (HTTP 400) → falls through to `HALT "unhandled reject … code None"` instead of RETRY-within-window (stalls the whole drain on a transient clock skew); `invalid_signature` (403) → dead-letter via the status branch instead of the intended integrity HALT. | Two changes in `relay/reject.py`: (1) read the code from `response.body.get("reason")` (iplanic's actual key), keeping `reject_code`/`code` as fallbacks. (2) **⚠ correction (independent review):** the reason-read at line 57 is **unreachable for `invalid_signature`** because the `status == 403` branch (line 53) returns `DEAD_LETTER` first — so reading `reason` alone fixes only `timestamp_skew`. Reorder so the integrity reason codes (`invalid_signature`/`schema_invalid`) are checked **before** the generic 403 dead-letter branch (or special-case them inside it) → `HALT`. Add a cross-repo contract test feeding iplanic's real `{"reason":"timestamp_skew"}` (400→RETRY) and `{"reason":"invalid_signature"}` (403→HALT). |

### P2 (HIGH — deployment contract; jointly owned with iplanic PLAN-100)

| ID | Finding | Fix |
| --- | --- | --- |
| B2 | Dispatch is `401` unless `dispatch_token_id` is set on the registration: iplanic attaches `Authorization` **only when** `dispatch_token_id` is present, but the runner receiver bearer is mandatory (won't start without a token). Omit it → 100% of dispatches fail. | Document the hard requirement in `framework/remote/REMOTE_EXECUTOR_CONTRACT.md`: every registration MUST set `dispatch_token_id`, resolving to the runner's `IOPS_RECEIVER_TOKEN`. (iplanic side adds a warn-on-unset — PLAN-100.) Optionally: on receiver startup, log the expected token-id binding for operator verification. |
| B4-runner | Ingestion auth-mode + HMAC key provisioning must align with iplanic. Runner sends a static `IOPS_IPLANIC_TOKEN` and has no OIDC path; `receiver_key_id` must equal the registered `log_ingest_key_id` with `IOPS_SIGNING_KEY` provisioned to iplanic. | Contribute the runner's half of the deployment-contract doc (static-token mode required, key-id binding). Cross-referenced from iplanic PLAN-100 B4. |

### P3 (MEDIUM — lifecycle / robustness)

| ID | Finding | Fix |
| --- | --- | --- |
| M-wall | `max_wall_s` budget can never fire: `usage["wall_s"]` is compared but `wall_s` is never written anywhere; no executor call takes a timeout. A hung task holds a `slots` semaphore permit forever → receiver answers `503 receiver_busy` permanently. | Measure wall time around the executor call and write `usage["wall_s"]`; pass a wall-clock timeout into `RuntimeClient.run_task` / `ModelClient.complete` (or wrap the executor call) so `BUDGET.TIME_EXCEEDED` can fire and the slot is released. |
| M-ws | No workspace cleanup: `provision_workspace` does a full clone per task and only `rmtree`s on same-key re-run; no GC of completed runs → disk fills. | Remove the per-task workspace after the run settles (success or fail), or add a bounded retention/GC of `<root>/<run_id>` dirs. |
| M-relay | Relay DB grows unbounded: `delivery`/`identity`/`accepted_task` rows are only inserted/updated, never pruned; a `503`-at-capacity dispatch still writes an `accepted` row (accept precedes the slot check). | Add a retention/prune path (age- or count-bounded `DELETE` of settled `delivery`/`accepted_task` rows) run on `sync` or a periodic sweep. |
| M-crash | Crash mid-run orphans a task in `running`: re-dispatch short-circuits as duplicate (`202`), signed events sit undrained until an operator `sync`. iplanic already got its `202` and won't retry. | Add auto-recovery: on receiver startup (or next `accept_task`), re-drain tasks stuck in `running` past a threshold; document the recovery contract. (This is the deferred PLAN-023+ follow-on.) |
| M-body | No request body size limit; `int(Content-Length)` with no `try` → a non-numeric header raises uncaught `ValueError`, killing the handler thread; a huge declared length forces a large blocking read. | Wrap the `int()` in `try/except` → `400`; enforce a max body size → `413`. (Auth is checked first, so this is authenticated-only — MEDIUM.) |
| M-budget-parity | Budget pre-check parity drift: hermes `ApiExecutor` checks budget before spending; claude `HostRuntimeExecutor` has no pre-check → runs one extra task after budget is blown. | Add the pre-spend budget check to `HostRuntimeExecutor` so both engines refuse when already over budget. |
| M-rotation | **Key rotation is one-sided (added — final-review coverage gap).** The runner signs every event with a single static `hmac-sha256` key hardcoded at `ledger/events.py:79-80` (`algorithm="hmac-sha256"`, one `key_id`); it has no ed25519 path and no rotation, while iplanic already supports `signing_keys[]` windows + `revoked` + ed25519 self-cert. There is no way for the emitter to roll a key without downtime. | Add a key-rotation path on the emitter (resolve the active `key_id`/`key` from config that can name >1 key with a validity window), and document the rotation runbook in `REMOTE_EXECUTOR_CONTRACT.md`. Optionally add the ed25519 signing option to match the standard's capability. Non-blocking for the first deployment (single-key works) but required before a key can be rotated in production. |

### P4 (spec conformance — depends on iplan-standard PLAN-0001 tag)

| ID | Finding | Fix |
| --- | --- | --- |
| S4 | Pinned at `iplan/v0.1.0`, three releases stale; **no L1 provenance verification on `main`** — a dispatch is accepted if the transport bearer matches, regardless of a missing/forged `intake_control.provenance`. `dispatch_token_id` (v0.3.0) and `intake_control.provenance` (v0.4.0) unabsorbed. | After PLAN-0001 tags `iplan/v0.5.0`: bump the pin in `sync/check-drift.sh` and both `security/iplanic_signing.py` headers + `REMOTE_EXECUTOR_CONTRACT.md`; run `sync/check-drift.sh` to confirm the byte-copyable surface still matches. **Decide L1 per the SINGLE OWNER — iplan-standard PLAN-0001 M6** (do NOT decide this independently; the ecosystem L1 normative status is owned there so the runner and iplanic don't diverge): if M6 ratifies L1 as normative, merge PLAN-024 (the intake-provenance gate on branch `plan/PLAN-024_l1-intake-provenance-gate`) to add initiator-signature verification; if M6 makes L1 optional, record the runner's opt-out in DECISIONS **citing M6**. |
| S5 | The drift-check that pins iplan-standard (`sync/check-drift.sh`) is orphaned — referenced only in docs, never wired into CI or pre-commit; the one CI drift workflow polices the CI canon, not the standard pin. | Wire `sync/check-drift.sh` into `scripts/pre_push_check.sh` and/or a CI job so an advancing standard is caught automatically. |
| M2-name | `intake_control` name collision: runner's `intake_control` (iops intake manifest on `document_type: iplan-intake`) vs the standard's `intake_control.provenance` (L1). Different document types, but the field name is overloaded. | Document the distinction in `REMOTE_EXECUTOR_CONTRACT.md`; ensure the runner never mis-ingests a standard `iplan-document` as its intake shape. Re-evaluate under the S4 L1 decision. |
| L-ver | `framework/VERSION 0.14.0` (runner's own execution-contract SemVer) collides numerically with the consumed `iplan/v0.x` line with no documented mapping; engine `VERSION 0.13.0` skews from `FRAMEWORK_SPEC_VERSION 0.14.0`. | Add a mapping note to `README.md`/`ROADMAP.md`: `framework/VERSION` is the runner execution contract; the consumed standard tag is separate (state the pinned tag explicitly). |
| M-taskschema | **Task-payload contract unenforced on the runner (added — final-review coverage gap).** The runner holds **no copy** of the standard's `task.schema.json` — it only references it in comments (`receiver/__init__.py:4`, `payload_rules.py:20`) and does loose non-empty validation. A future `task.schema.json` change breaks the runner silently with no failing test. | After the S4 re-pin, vendor `task.schema.json` from the pinned tag and add a runner-side conformance test that validates a representative dispatch payload against it (mirrors how iplanic validates on build). Keeps both sides of the dispatch contract pinned to the same schema. |

### P6 (integration harness — joint with iplanic PLAN-100)

| ID | Finding | Fix |
| --- | --- | --- |
| INT-1 | **No true cross-repo integration test (added — final-review coverage gap).** Both sides are tested only in isolation with mocks — the runner's `test_integration.py` / `test_iplanic_transport.py` mock iplanic, and iplanic's tests mock the runner. No test drives the real dispatch → execute → signed-event → ingest → project loop across both processes, so the B2/B3/B4 wire mismatches were invisible to CI. | Stand up a cross-repo integration harness (either engine's receiver + a real iplanic app instance over loopback) exercising: register → dispatch (with `dispatch_token_id`) → clone → execute (stub client) → emit signed event → iplanic ingest → projection leaves `Queued`. This is the test that would have caught B2 and B3. Owned jointly; the harness can live in either repo's CI or a small shared fixture. |

### P5 (LOW — docs / hygiene)

| ID | Finding | Fix |
| --- | --- | --- |
| M4-dup | Duplicate `PLAN-023` files (`_consume-iplan-standard` D-0023, `_receiver-executor-wiring` D-0025) and contested `PLAN-024` number (HANDOFF says "client adapters"; the intake-gate branch also holds PLAN-024). | Renumber one `PLAN-023` file to a free number; reconcile `PLAN-024` in HANDOFF + TODO so one meaning wins. |
| L-handoff | `plans/HANDOFF.md` dated 2026-06-27, omits the relay-store flake fix, auto-merge caller, and Wave 3 adoption present in CHANGELOG. | Refresh HANDOFF to current `main`. |
| L-leak | Repro friction: a bare `pytest` fails collection (`ModuleNotFoundError: iplan_claude`) — needs `pip install -e` or `PYTHONPATH=platforms/<engine>/src`. | Document the test-run command in README/CONTRIBUTING. |

## Verification

- Both engines' suites green after each change:
  `PYTHONPATH=platforms/claude/src python -m pytest platforms/claude -q` (142) and
  the hermes twin (142); `tests/conformance` (26 / 515 subtests).
- New tests: B1 scheme-rejection matrix, B3 envelope-classification against
  iplanic's real `{"reason":…}` bodies, M-body malformed `Content-Length`.
- Keep the two engines byte-identical in the shared modules (a parity diff in CI).

## Cross-repo sequencing

B1, B3, and all P3 lifecycle items are independent — start now. P4 (S4 re-pin)
blocks on iplan-standard PLAN-0001 tagging `iplan/v0.5.0`. B2/B4 pair with
iplanic PLAN-100's deployment-contract + warn-on-unset work.

## Claim ledger

| # | Claim | Symbol | Citation |
| --- | --- | --- | --- |
| 1 | `clone()` runs `git clone --no-single-branch <url>` with an unvalidated `url` and no `--` separator | `clone` | platforms/hermes/src/iplan_hermes/vcs/git.py:34 |
| 2 | `checkout` of `ref` also has no `--` separator | `checkout` | platforms/hermes/src/iplan_hermes/vcs/git.py:40 |
| 3 | `validate_payload` only non-empty-checks repository fields; no URL scheme allow-list | `_REPOSITORY_FIELDS` | platforms/hermes/src/iplan_hermes/validation/payload_rules.py:22 |
| 4 | `classify()` reads reject code from `reject_code`/`code`, not `reason` | `classify` | platforms/hermes/src/iplan_hermes/relay/reject.py:45 |
| 5 | `timestamp_skew` intended RETRY-within-window; unknown code → HALT | `timestamp_skew` | platforms/hermes/src/iplan_hermes/relay/reject.py:58 |
| 6 | `invalid_signature` intended integrity HALT | `invalid_signature` | platforms/hermes/src/iplan_hermes/relay/reject.py:63 |
| 7 | `wall_s` is only read in the comparison, never written | `wall_s` | platforms/hermes/src/iplan_hermes/budget.py:32 |
| 8 | Receiver bearer mandatory; `Content-Length` parsed with no try/except | `Content-Length` | platforms/hermes/src/iplan_hermes/receiver/http.py:69 |
| 9 | Slot semaphore acquired after auth; a hung task holds a permit | `slots.acquire` | platforms/hermes/src/iplan_hermes/receiver/http.py:91 |
| 10 | `provision_workspace` only `rmtree`s the dest on same-key re-run (no post-run GC) | `provision_workspace` | platforms/hermes/src/iplan_hermes/receiver/service.py:61 |
| 11 | Relay store `accepted_task`/`delivery`/`identity` created but never pruned (no DELETE/VACUUM) | `accepted_task` | platforms/hermes/src/iplan_hermes/relay/store.py:67 |
| 12 | Standard pin is `iplan/v0.1.0` (three releases stale) | `IPLAN_STANDARD_TAG` | sync/check-drift.sh:14 |
| 13 | Receiver refuses to start on an empty token (B2 startup guard) | `refusing to start` | platforms/hermes/src/iplan_hermes/receiver/http.py:114 |
| 14 | hermes `ApiExecutor.execute` pre-checks budget before spending; claude has none | `pre = check` | platforms/hermes/src/iplan_hermes/executor/api.py:47 |
| 15 | 403 branch returns DEAD_LETTER before the reason code is read (B3 ordering) | `DEAD_LETTER, "registration/scope rejected"` | platforms/hermes/src/iplan_hermes/relay/reject.py:74 |
| 16 | Runner signs with a single static `hmac-sha256` key/`key_id` — no rotation, no ed25519 (M-rotation) | `algorithm="hmac-sha256"` | platforms/hermes/src/iplan_hermes/ledger/events.py:79 |
| 17 | Runner holds no `task.schema.json`; only comment references + loose validation (M-taskschema) | `task.schema.json` | platforms/hermes/src/iplan_hermes/validation/payload_rules.py:20 |

## Review log

### Pass 1 — 2026-07-09 — author (self)

Drafted from the pre-prod review; verified citations 1-12 by opening each file
(store.py prune-absence confirmed by grep count 0). B1 and B3 are the two I would
land first. All code fixes apply to both engines.
**Result:** pending independent review (Pass 2 required before ready).

### Pass 2 — 2026-07-09 — independent

Fresh-context adversarial review against both engine trees. All 12 original
citations verified accurate. **Load-bearing findings, all folded above:**

- **B1 checkout fix was wrong** — `git checkout -- <ref>` treats `<ref>` as a
  pathspec, breaking every checkout. Corrected to trailing `--` / rev-parse; `--`
  moved *after* the URL in clone. (git-semantics)
- **B3 fix was insufficient** — the `status==403` branch (reject.py:54) returns
  DEAD_LETTER before the reason is read, so `invalid_signature` stays mis-routed;
  fix now reorders integrity codes ahead of the 403 branch.
- **B1 breaks existing `file://` receiver fixtures** (`test_task_receiver.py` et al.
  via `.as_uri()`) — added the test-only scheme exemption to scope.
- **Parity overstated** — `receiver/service.py` differs by 3 engine-name lines;
  parity-diff must exclude them. (Corrected in the parity note.)
- **Uncited-but-true** — added ledger rows 13 (startup guard), 14 (budget
  pre-check asymmetry), 15 (403 branch order).

### Pass 3 — 2026-07-09 — independent (confirmation)

Fresh-context re-review of the reworked B1/B3 fix text, the corrected parity note,
and the three new ledger rows (13-15) against source. Confirmed the checkout guard
is git-correct (trailing `--` / rev-parse), the B3 reorder reaches the integrity
codes ahead of the 403 branch, and rows 13-15 resolve. No new load-bearing
findings.

### Pass 4 — 2026-07-09 — program coverage cross-check

Final program-level review across all three plans found three pre-prod findings
that had fallen through to no plan; all added here: **M-rotation** (runner
single-static-key signing, `events.py:79`), **M-taskschema** (no runner-side
`task.schema.json`, `payload_rules.py:20`), and **INT-1** (no true cross-repo
integration harness — both sides mock the other). Ledger rows 16-17 added; INT-1
is doc-referenced against existing `test_integration.py`. (A2A/MCP framing
confirmed already tracked in iplanic PLAN-100.)
**Result:** ready.
