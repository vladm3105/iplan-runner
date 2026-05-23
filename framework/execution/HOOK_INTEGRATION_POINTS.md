# Hook Integration Points

Where a host platform (e.g. Claude Code hooks, an MCP server, a CI step) may
call into an engine, and the authority limits on each.

## Integration points

| Point | Fires | Engine action | Authority |
|-------|-------|---------------|-----------|
| `session_start` | Agent begins work | Load/verify ledger; bind source IPLAN | Read ledger; create if absent |
| `pre_task` | Before a task | Acquire lease; append `task_started` event | Append-only |
| `post_edit` | After a file change | Append `file_edited` event with `touched_paths` | Append-only; reject paths outside `allowed_roots` |
| `evidence` | A check produced a result | Append `execution_evidence` | Append-only |
| `pre_complete` | Agent wants to mark complete | Run verification gate | **May veto** completion |
| `reconcile` | End of session | Update reconciliation counts | Append-only |

## Authority limits

- Hooks may **append** to the ledger and **read** it. They may **not** mutate or
  delete prior entries.
- The `pre_complete` hook is the only point that may **block** progress, and only
  by failing the verification gate — never by silently editing state.
- A hook must never write outside `isolation_scope.allowed_roots`, and must
  never cross `client_id` / `project_id` boundaries.
