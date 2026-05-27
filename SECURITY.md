# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue or PR
for a suspected vulnerability.

- Use GitHub's **private vulnerability reporting** for this repository
  (**Security → Report a vulnerability**), which opens a private advisory with
  the maintainers.

Include: affected component (engine + path), version (`framework/VERSION`), a
reproduction, and the impact you observed. We aim to acknowledge a report within
a few business days and will coordinate a fix and disclosure timeline with you.

## Scope

This framework is the execution / operations plane. Its trust boundary, threat
model, and the tests backing each mitigation are documented in:

- [`framework/security/SECURITY_MODEL.md`](framework/security/SECURITY_MODEL.md)
  — the model (authenticated ledger, layered authz, sandbox, output-is-data).
- [`docs/SECURITY_REVIEW.md`](docs/SECURITY_REVIEW.md) — per-threat mitigation +
  its test, plus residual / deferred risks.

## Supported versions

The `framework/` contract is stable under SemVer from `v1.0.0`. Security fixes
target the latest released minor.
