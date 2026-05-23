"""Replay every golden vector through every importable engine."""
from __future__ import annotations

import unittest

import yaml

import _spec


class VectorReplayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engines = _spec.load_engines()
        if not self.engines:
            self.skipTest("no engines importable")
        self.severity = {r["id"]: r["severity"] for r in _spec.rule_catalog()["rules"]}

    def test_vectors(self) -> None:
        for document_path, expect_path in _spec.vector_pairs():
            document = yaml.safe_load(document_path.read_text())
            expected = yaml.safe_load(expect_path.read_text())
            expected_rules = set(expected.get("rule_ids") or [])
            for engine_id, engine in self.engines.items():
                with self.subTest(engine=engine_id, vector=document_path.stem):
                    result = engine.validate(document)
                    self.assertEqual(result["status"], expected["status"])
                    self.assertEqual(
                        {f["rule_id"] for f in result["findings"]}, expected_rules
                    )
                    for finding in result["findings"]:
                        self.assertEqual(
                            finding["severity"], self.severity[finding["rule_id"]]
                        )


if __name__ == "__main__":
    unittest.main()
