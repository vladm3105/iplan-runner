# Config Contract

Engine configuration is merged from a **YAML file** + **environment overrides**
into the engine `Config`. **Secrets never live in the file or the repo** — they
come from the environment (`secrets_from_env`, PLAN-007). `load_config(path,
env)` produces the `Config`; file values are the base, env keys override.

## Common keys (engine-agnostic)

| Key | Meaning |
|-----|---------|
| `exec_ready_min` | intake approval threshold (default 90) |
| `max_retries` / `backoff_base` | saga retry policy (PLAN-005) |
| `signing_key` | ledger HMAC key (PLAN-007) — sourced from env, never the file |
| `budget` | `{max_tokens, max_cost_usd, max_wall_s}` (RESOURCE_GOVERNANCE); `None` = unlimited |
| `telemetry.otlp_endpoint` | OTel exporter endpoint (monitoring) |
| `secrets` | redaction list — sourced from env (`IOPS_SECRET_*`) |

## Per-engine executor keys

- **`hermes` (ApiExecutor):** `provider` (e.g. `anthropic` / `litellm`), `model`,
  `api_base`. The API key is an env secret (e.g. `ANTHROPIC_API_KEY`), never the
  file.
- **`claude` (HostRuntimeExecutor):** `runtime` (host-runtime selector),
  `hooks` (hook wiring), `workspace` defaults.

## Sourcing precedence

1. File (`load_config(path)`) — non-secret structure/defaults.
2. Environment overrides — for deploy-specific values.
3. Secrets — **only** from env (`signing_key`, API keys, `IOPS_SECRET_*`); a
   secret found in the config file is an error to surface (don't commit secrets).
