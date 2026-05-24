# Resource Governance

A **budget** caps the resources a run may consume — token count, cost, and
wall-time — so a live executor (PLAN-008) cannot run away. The **decision** is a
pure function (parity-pinned, vector'd); enforcement happens **inside** the
executor (the run loop is unchanged).

## Budget

```python
@dataclass
class Budget:
    max_tokens: int | None = None     # None = unlimited
    max_cost_usd: float | None = None
    max_wall_s: float | None = None
```

A default `Budget()` is unlimited, so a default run enforces nothing (prior
phases unchanged).

## Decision

```
check(budget, usage) -> {allowed: bool, reason: str}
usage = {tokens, cost_usd, wall_s}
```

Evaluated in order; the first exceeded limit decides:

| Reason | When |
|--------|------|
| `BUDGET.TOKENS_EXCEEDED` | `max_tokens` set and `usage.tokens > max_tokens` |
| `BUDGET.COST_EXCEEDED` | `max_cost_usd` set and `usage.cost_usd > max_cost_usd` |
| `BUDGET.TIME_EXCEEDED` | `max_wall_s` set and `usage.wall_s > max_wall_s` |
| `BUDGET.OK` | within every set limit (or all unlimited) |

(These are decision outputs, not document-`validate()` findings — like the
sandbox/authz codes.)

## Enforcement

The executor is constructed with a `Budget` and tracks **cumulative** usage
across the tasks of one run; it calls `check` before each model call. When the
result is not `BUDGET.OK`, the task is **blocked** (non-retriable) and the run
reconciles short — broken/over-budget work is never marked complete.
