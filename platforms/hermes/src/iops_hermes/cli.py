"""``iops-hermes`` command-line interface."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .audit.report import build_audit_report
from .engine import HermesEngine
from .monitoring.slo import evaluate_slos


def _load(path: str) -> dict[str, Any]:
    data: Any = yaml.safe_load(Path(path).read_text())
    return data if isinstance(data, dict) else {}


def _emit(result: Any) -> None:
    print(json.dumps(result, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="iops-hermes")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ledger = sub.add_parser("ledger", help="ledger operations")
    p_ledger.add_argument("action", choices=["validate"])
    p_ledger.add_argument("path")

    p_gate = sub.add_parser("gate", help="run a verification gate")
    p_gate.add_argument("action", choices=["run"])
    p_gate.add_argument("ledger")
    p_gate.add_argument("gate")

    p_audit = sub.add_parser("audit", help="build an audit report")
    p_audit.add_argument("action", choices=["report"])
    p_audit.add_argument("baseline")
    p_audit.add_argument("comparison")

    p_monitor = sub.add_parser("monitor", help="monitoring operations")
    p_monitor.add_argument("action", choices=["validate", "slo-check"])
    p_monitor.add_argument("manifest")
    p_monitor.add_argument("samples", nargs="?")

    args = parser.parse_args(argv)
    engine = HermesEngine()

    if args.command == "ledger":
        result = engine.validate(_load(args.path))
        _emit(result)
        return 0 if result["status"] != "fail" else 1

    if args.command == "gate":
        result = engine.run_gate(_load(args.ledger), _load(args.gate))
        _emit(result)
        return 0 if result["status"] == "passed" else 1

    if args.command == "audit":
        report = build_audit_report(_load(args.baseline), _load(args.comparison))
        validation = engine.validate(report)
        _emit({"report": report, "validation": validation})
        return 0 if validation["status"] != "fail" else 1

    if args.command == "monitor":
        manifest = _load(args.manifest)
        if args.action == "validate":
            result = engine.validate(manifest)
            _emit(result)
            return 0 if result["status"] != "fail" else 1
        samples = _load(args.samples) if args.samples else {}
        _emit(evaluate_slos(manifest, samples))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
