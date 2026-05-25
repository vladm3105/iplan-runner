"""Cross-engine chain-orchestration parity (framework/conformance/chains)."""

from __future__ import annotations

import itertools
import unittest
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import _spec
import yaml


def _make_clock(start: str) -> Callable[[], str]:
    base = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    counter = itertools.count()
    return lambda: (base + timedelta(seconds=next(counter))).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_ids() -> Callable[[str], str]:
    counters: dict[str, int] = {}

    def ids(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}{counters[prefix]}"

    return ids


def _noop_sleep(_seconds: float) -> None:
    return None


def _project(chain_ledger: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_order": chain_ledger["execution_order"],
        "iplan_chain": {n["iplan_id"]: {"reconciled": n["reconciled"]} for n in chain_ledger["iplan_chain"]},
        "chain_reconciliation": chain_ledger["chain_reconciliation"],
        "chain_status": chain_ledger["chain_control"]["status"],
    }


def _scenarios() -> list[Path]:
    root = _spec.FRAMEWORK / "conformance" / "chains"
    return sorted(root.glob("*/scenario.yaml"))


class ChainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engines = _spec.load_engines()
        if not self.engines:
            self.skipTest("no engines importable")

    def test_chains(self) -> None:
        for scenario_path in _scenarios():
            scenario = yaml.safe_load(scenario_path.read_text())
            expect = yaml.safe_load((scenario_path.parent / "expect.yaml").read_text())
            ledgers = []
            for engine_id, engine in self.engines.items():
                outcomes = scenario["mock_outcomes"]
                executor_for = lambda iid, e=engine: e.mock_executor(outcomes.get(iid, {}))
                result = engine.run_chain(
                    scenario["chain"],
                    scenario["iplans"],
                    executor_for,
                    clock=_make_clock(scenario["clock_start"]),
                    ids=_make_ids(),
                    sleep=_noop_sleep,
                )
                with self.subTest(engine=engine_id, scenario=scenario_path.parent.name):
                    self.assertEqual(_project(result.chain_ledger), expect)
                ledgers.append(result.chain_ledger)
            if len(ledgers) >= 2:
                with self.subTest(scenario=scenario_path.parent.name, check="differential"):
                    for ledger in ledgers[1:]:
                        self.assertEqual(ledger, ledgers[0])


if __name__ == "__main__":
    unittest.main()
