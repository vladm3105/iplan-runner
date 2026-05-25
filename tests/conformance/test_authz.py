"""Cross-engine authorization-decision parity (framework/conformance/authz)."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path

import _spec
import yaml


def _cases() -> list[Path]:
    root = _spec.FRAMEWORK / "conformance" / "authz"
    return sorted(p for p in root.iterdir() if p.is_dir())


def _authz_fns() -> dict[str, object]:
    fns: dict[str, object] = {}
    for entry in _spec.registry().get("engines", []):
        try:
            module = importlib.import_module(f"{entry['package']}.security.authz")
        except Exception:
            continue
        fns[entry["id"]] = module.authorize
    return fns


class AuthzTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fns = _authz_fns()
        if not self.fns:
            self.skipTest("no engines importable")

    def test_authorize_parity(self) -> None:
        for case in _cases():
            inp = yaml.safe_load((case / "input.yaml").read_text())
            expect = yaml.safe_load((case / "expect.yaml").read_text())
            decisions = []
            for engine_id, authorize in self.fns.items():
                decision = authorize(inp["actor"], inp["action"])
                with self.subTest(engine=engine_id, case=case.name):
                    self.assertEqual(decision, expect)
                decisions.append((decision["allowed"], decision["reason"]))
            if len(decisions) >= 2:
                with self.subTest(case=case.name, check="differential"):
                    self.assertEqual(len(set(decisions)), 1)


if __name__ == "__main__":
    unittest.main()
