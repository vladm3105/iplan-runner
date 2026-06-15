"""Cross-engine ledger-signing parity (framework/conformance/signing)."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path

import _spec
import yaml


def _cases() -> list[Path]:
    root = _spec.FRAMEWORK / "conformance" / "signing"
    return sorted(p for p in root.iterdir() if p.is_dir())


def _sign_fns() -> dict[str, object]:
    fns: dict[str, object] = {}
    for entry in _spec.registry().get("engines", []):
        try:
            module = importlib.import_module(f"{entry['package']}.security.signing")
        except Exception:
            continue
        fns[entry["id"]] = module.sign_event
    return fns


class SigningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fns = _sign_fns()
        if not self.fns:
            self.skipTest("no engines importable")

    def test_sign_event_parity(self) -> None:
        for case in _cases():
            inp = yaml.safe_load((case / "input.yaml").read_text())
            expect = yaml.safe_load((case / "expect.yaml").read_text())
            signatures = []
            for engine_id, sign_event in self.fns.items():
                sig = sign_event(inp["event"], inp["key"])
                with self.subTest(engine=engine_id, case=case.name):
                    self.assertEqual(sig, expect["signature"])
                signatures.append(sig)
            if len(signatures) >= 2:
                with self.subTest(case=case.name, check="differential"):
                    self.assertEqual(len(set(signatures)), 1)


if __name__ == "__main__":
    unittest.main()
