## Summary

<!-- 1–2 sentences: what changes and why. -->

## Changes

-

## Testing

- [ ] Conformance suite passes (`python -m unittest discover -s tests/conformance`)
- [ ] Engine tests pass (`pytest platforms/<engine>`)
- [ ] Lint + types clean (`ruff check platforms`, `mypy --strict platforms/*/src`)

## Checklist

- [ ] One logical change per PR; conventional commit prefix
      (`feat`/`fix`/`test`/`docs`/`chore`/`refactor`)
- [ ] Docs updated with code — `CHANGELOG.md` (`[Unreleased]` entry) for any
      change touching `framework/` or an engine's `src/`; CI gates this
      (`[no-changelog]` in the commit message if genuinely not user-facing)
- [ ] `framework/` contract changes follow SemVer and update `framework/VERSION`
      + every engine's `FRAMEWORK_SPEC_VERSION`
- [ ] No secrets or local absolute paths introduced
