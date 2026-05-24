"""Replay execution scenarios: per-engine projection + cross-engine differential."""
from __future__ import annotations

import copy
import itertools
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

import _spec


def _normalize(ledger: dict[str, Any]) -> dict[str, Any]:
    """Strip the one legitimately engine-specific field (lease agent_id, the
    engine's own identity; it is not part of the hash chain) so the differential
    compares engines modulo identity."""
    normalized = copy.deepcopy(ledger)
    for lease in normalized.get("agent_leases", []):
        lease["agent_id"] = "<engine>"
    return normalized


def _make_clock(start: str) -> Callable[[], str]:
    base = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    counter = itertools.count()
    return lambda: (base + timedelta(seconds=next(counter))).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_ids() -> Callable[[str], str]:
    counters: dict[str, int] = {}

    def ids(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}{counters[prefix]}"

    return ids


def _project(engine: Any, result: Any) -> dict[str, Any]:
    ledger = result.ledger
    tasks = {
        t["task_id"]: {"status": t["status"], "has_evidence": bool(t["evidence_refs"])}
        for t in ledger["task_ledger"]
    }
    log_events = [
        {
            "event_type": e["event_type"],
            "subject_id": e["subject_id"],
            "touched_paths": e.get("touched_paths", []),
        }
        for e in ledger["execution_log"]
    ]
    saga = {
        t["task_id"]: {"status": t["status"], "attempts": t.get("attempts", 1)}
        for t in ledger["saga_journal"]
    }
    handover = engine.build_handover(ledger, result.gate_result)
    return {
        "tasks": tasks,
        "reconciliation": ledger["reconciliation"],
        "log_events": log_events,
        "saga": saga,
        "gate": result.gate_result["status"],
        "handover_status": handover["result"]["status"],
    }


def _noop_sleep(_seconds: float) -> None:
    return None


def _scenarios() -> list[Path]:
    root = _spec.FRAMEWORK / "conformance" / "scenarios"
    return sorted(root.glob("*/scenario.yaml"))


class ScenarioTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engines = _spec.load_engines()
        if not self.engines:
            self.skipTest("no engines importable")

    def test_scenarios(self) -> None:
        for scenario_path in _scenarios():
            scenario = yaml.safe_load(scenario_path.read_text())
            expect = yaml.safe_load((scenario_path.parent / "expect.yaml").read_text())
            ledgers = []
            for engine_id, engine in self.engines.items():
                result = engine.run(
                    scenario["intake"],
                    engine.mock_executor(scenario["mock_outcomes"]),
                    clock=_make_clock(scenario["clock_start"]),
                    ids=_make_ids(),
                    sleep=_noop_sleep,
                    max_retries=scenario.get("max_retries", 0),
                )
                with self.subTest(engine=engine_id, scenario=scenario_path.parent.name):
                    self.assertEqual(_project(engine, result), expect)
                ledgers.append(result.ledger)
            if len(ledgers) >= 2:
                with self.subTest(scenario=scenario_path.parent.name, check="differential"):
                    baseline = _normalize(ledgers[0])
                    for ledger in ledgers[1:]:
                        self.assertEqual(_normalize(ledger), baseline)


if __name__ == "__main__":
    unittest.main()
