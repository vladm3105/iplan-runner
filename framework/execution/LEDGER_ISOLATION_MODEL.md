# Ledger Isolation Model

Every ledger is bound to an isolation scope so execution cannot leak across
tasks, projects, or clients.

## Scope

```yaml
isolation_scope:
  client_id: "client-a"
  project_id: "project-x"
  allowed_roots: ["src/", "tests/"]
```

- `client_id` / `project_id` — the tenancy boundary. Every `execution_log` event
  carries its own `client_id` / `project_id`; a mismatch with the ledger scope
  is `ISOLATION.EVENT_SCOPE_MISMATCH`.
- `allowed_roots` — the only path prefixes an agent may touch. Any
  `touched_paths` entry outside every root is `ISOLATION.PATH_OUTSIDE_ROOTS`.
- A ledger missing any of `client_id` / `project_id` / `allowed_roots` is
  `ISOLATION.SCOPE_MISSING`.

## Boundaries

| Level | Boundary | Violation |
|-------|----------|-----------|
| Task | A lease scopes work to one `task_id` | overlapping leases (`LEDGER.LEASE_OVERLAP`) |
| Project | `project_id` + `allowed_roots` | out-of-roots edit / wrong project on an event |
| Client | `client_id` | event for a different client |

## Guarantee

Two ledgers for different `(client_id, project_id)` pairs can be executed
concurrently with no shared mutable state. Path containment is checked per event,
so a single stray edit outside `allowed_roots` fails the gate
(`GATE-LEDGER-004`).
