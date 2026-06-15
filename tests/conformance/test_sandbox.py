"""Cross-engine path-jail decision parity (framework/conformance/sandbox)."""

from __future__ import annotations

import unittest
from pathlib import Path

import _spec
import yaml


def _cases() -> list[Path]:
    root = _spec.FRAMEWORK / "conformance" / "sandbox"
    return sorted(p for p in root.iterdir() if p.is_dir())


class SandboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engines = _spec.load_engines()
        if not self.engines:
            self.skipTest("no engines importable")

    def test_classify_parity(self) -> None:
        for case in _cases():
            inp = yaml.safe_load((case / "input.yaml").read_text())
            expect = yaml.safe_load((case / "expect.yaml").read_text())
            decisions = []
            for engine_id, engine in self.engines.items():
                decision = engine.classify_path(inp["path"], inp["allowed_roots"], inp.get("forbidden_paths", []))
                with self.subTest(engine=engine_id, case=case.name):
                    self.assertEqual(decision, expect)
                decisions.append((decision["allowed"], decision["reason"]))
            if len(decisions) >= 2:
                with self.subTest(case=case.name, check="differential"):
                    self.assertEqual(len(set(decisions)), 1)


if __name__ == "__main__":
    unittest.main()
