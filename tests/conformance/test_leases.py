"""Cross-engine lease can_acquire decision parity (framework/conformance/leases)."""
from __future__ import annotations

import importlib
import unittest
from pathlib import Path

import yaml

import _spec


def _cases() -> list[Path]:
    root = _spec.FRAMEWORK / "conformance" / "leases"
    return sorted(p for p in root.iterdir() if p.is_dir())


def _can_acquire_fns() -> dict[str, object]:
    fns: dict[str, object] = {}
    for entry in _spec.registry().get("engines", []):
        try:
            module = importlib.import_module(f"{entry['package']}.orchestrator.leases")
        except Exception:
            continue
        fns[entry["id"]] = module.can_acquire
    return fns


class LeaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fns = _can_acquire_fns()
        if not self.fns:
            self.skipTest("no engines importable")

    def test_can_acquire_parity(self) -> None:
        for case in _cases():
            inp = yaml.safe_load((case / "input.yaml").read_text())
            expect = yaml.safe_load((case / "expect.yaml").read_text())
            decisions = []
            for engine_id, can_acquire in self.fns.items():
                allowed = can_acquire(inp["existing_leases"], inp["task_id"], inp["now"])
                with self.subTest(engine=engine_id, case=case.name):
                    self.assertEqual(allowed, expect["allowed"])
                decisions.append(allowed)
            if len(decisions) >= 2:
                with self.subTest(case=case.name, check="differential"):
                    self.assertEqual(len(set(decisions)), 1)


if __name__ == "__main__":
    unittest.main()
