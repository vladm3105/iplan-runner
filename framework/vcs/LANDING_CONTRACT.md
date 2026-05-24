# Landing Contract

How a green, reconciled run is **landed** into version control — the
**"committed"** half of SDD's "committed + green" definition of done.

## Flow

`land(ledger, workspace, *, branch, message, author, clock, ids)`:

1. **No-op if nothing changed.** If `has_changes(workspace)` is false (e.g. a
   `MockExecutor` run touched no files), `land` does nothing: no commit,
   `requires_landing` stays false, the green handover is unchanged.
2. **Commit.** Otherwise create/switch to `branch`, stage all changes, and commit
   with an explicit author (no reliance on global git identity).
3. **Record.** Append a commit to the ledger's `vcs.commits`
   (`{sha, message, at, touched_paths}`), append a `commit` execution-log event,
   set `ledger_control.requires_landing = true`.
4. **Re-gate.** Re-run the gate; with a commit recorded, `GATE-LEDGER-006`
   passes.

Landing is invoked **only when the run is green and reconciled** — broken or
incomplete work is never committed. The CLI: `run --land --branch <b>` over a
`--workspace` git repo.

## Commit record

```yaml
vcs:
  branch: "iops/iplan-001"
  commits:
    - sha: "<git object id>"
      message: "..."
      at: "<iso>"
      touched_paths: ["src/foo.py"]
```

## Validation (`LEDGER.NOT_COMMITTED`, GATE-LEDGER-006)

Fires iff `ledger_control.requires_landing` is true **and** `vcs.commits` is
empty. In the live flow `land` commits before setting `requires_landing`, so this
never trips for a real landed run — it is a **guard** against external /
hand-crafted ledgers that claim landing without a commit. The rule is otherwise a
no-op (every pre-landing ledger leaves `requires_landing` false), so it lives in
the default gate without affecting non-landing runs.

## Out of scope

Pushing to a remote and opening a pull request require a remote + authentication
(GitHub-specific) and are operator / CI integration — not part of this contract.
The framework records the **local** branch + commit; a PR can be opened from it
downstream. Merge-conflict resolution and rebasing are likewise out of scope; the
workspace is assumed clean for the run.
