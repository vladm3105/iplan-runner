# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Planning artifacts and architecture decisions (D-0001..D-0012).
- Engine-agnostic execution contract (`framework/execution/`): ledger,
  verification-gate, chain-ledger, and audit-report templates + agent-update,
  hook-integration, saga, and isolation protocol docs.
- OpenTelemetry-aligned post-implementation monitoring contract
  (`framework/monitoring/`).
- Engine-adapter contract, execution registry, fine-grained rule-ID catalog,
  and 24 golden conformance vectors (`framework/`).
- Two fully self-contained reference engines under `platforms/`: `hermes`
  (MCP-server engine) and `claude` (Claude Code engine, AGENT_UPDATE_PROTOCOL),
  each with ledger store + hash chain, validators, gate runner, audit
  generation, OTel-optional monitoring, SLO evaluation, and a CLI.
- Conformance suite (`tests/conformance/`): vector replay, cross-engine
  differential, strict-isolation, rule-catalog coverage, and spec-version parity.
