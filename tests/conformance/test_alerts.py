"""Cross-engine alert-evaluation parity (framework/conformance/alert)."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path

import _spec
import yaml


def _cases() -> list[Path]:
    root = _spec.FRAMEWORK / "conformance" / "alert"
    return sorted(p for p in root.iterdir() if p.is_dir())


def _eval_fns() -> dict[str, object]:
    fns: dict[str, object] = {}
    for entry in _spec.registry().get("engines", []):
        try:
            module = importlib.import_module(f"{entry['package']}.monitoring.alerts")
        except Exception:
            continue
        fns[entry["id"]] = module.evaluate_alerts
    return fns


class AlertTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fns = _eval_fns()
        if not self.fns:
            self.skipTest("no engines importable")

    def test_alert_parity(self) -> None:
        for case in _cases():
            inp = yaml.safe_load((case / "input.yaml").read_text())
            expect = yaml.safe_load((case / "expect.yaml").read_text())
            outcomes = []
            for engine_id, evaluate_alerts in self.fns.items():
                alerts = evaluate_alerts(inp["manifest"], inp["samples"])
                with self.subTest(engine=engine_id, case=case.name):
                    self.assertEqual(alerts, expect["alerts"])
                outcomes.append(repr(alerts))
            if len(outcomes) >= 2:
                with self.subTest(case=case.name, check="differential"):
                    self.assertEqual(len(set(outcomes)), 1)


if __name__ == "__main__":
    unittest.main()
