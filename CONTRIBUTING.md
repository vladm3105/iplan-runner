# Contributing

Thanks for your interest in `iplan-runner`. The framework is small and
opinionated; the conventions below keep it that way.

## Scope

This repo is the **execution / operations plane**. It consumes an approved
`IPLAN` from SDD (`aidoc-flow-framework`) and proves it ran. Architectural
changes touch the `framework/` contract; runtime changes touch the per-engine
`platforms/<engine>/` packages. The contract is **stable under SemVer** from
`v1.0.0` — breaking contract changes bump the major version (the conformance
suite is the gate).

## Development workflow

Captured in `CLAUDE.md`; in short:

1. **Plan first.** Drop a plan into `plans/` (start from
   `plans/PLAN-TEMPLATE.md`); it must pass **≥2 review passes** in its
   `## Review log` before implementation. **Size the plan to the problem** —
   ~N fixes for N discovered issues, not N speculative features. If a review
   pass surfaces more gaps than the original problem had, cut the surplus.
2. **One task per commit** (conventional prefixes: `feat` / `fix` / `test` /
   `docs` / `chore` / `refactor`).
3. **Verify before calling anything done** (see below).
4. **Strict engine isolation** (D-0011): each engine imports only the
   `framework/` spec, never another engine — code duplication is intentional.
5. **Parity is proven by golden vectors** (D-0012), not shared code. Never
   weaken a conformance check to make it pass; fix the engine.

See `plans/DECISIONS.md` for the architecture rationale.

## Set up

```bash
pip install -e "./platforms/hermes[dev]" -e "./platforms/claude[dev]"
pip install pre-commit && pre-commit install
```

## Verify

```bash
python -m unittest discover -s tests/conformance -v   # vectors + isolation + parity
pytest platforms/hermes platforms/claude -q           # engine + acceptance tests
ruff check platforms
mypy --strict platforms/hermes/src platforms/claude/src
pre-commit run --all-files
```

All must be green before opening a PR. CI re-runs the same suite plus CodeQL,
pip-audit, and gitleaks.

## Pull requests

- Target `main`. Keep the PR focused on one plan or one fix.
- Include a brief `## Summary` and a `## Test plan` (what you ran, what passed).
- For contract changes: link the relevant plan + bump `framework/VERSION`,
  registry `spec_version`, and both engines' `FRAMEWORK_SPEC_VERSION` together.
- **Update docs with code.** If the PR touches `framework/` or an engine's
  `src/`, `pyproject.toml`, or `FRAMEWORK_SPEC_VERSION`, update `CHANGELOG.md`
  in the same PR (`[Unreleased]` is enough). Also update `plans/HANDOFF.md`,
  `TODO.md`, `ROADMAP.md`, `README.md`, and `docs/**` as their content is
  affected. CI gates the `CHANGELOG.md` requirement; include `[no-changelog]`
  in a commit message when the change is genuinely not user-facing.

## Security

Do **not** report vulnerabilities via public issues or PRs. See
[`SECURITY.md`](SECURITY.md) for the private disclosure path; the threat model
and per-threat tests are in [`docs/SECURITY_REVIEW.md`](docs/SECURITY_REVIEW.md).

## License

Contributions are licensed under the **Apache License 2.0** (see
[`LICENSE`](LICENSE)). By submitting a contribution you agree it may be
distributed under those terms.
