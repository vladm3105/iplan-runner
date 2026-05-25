"""Cross-engine differential: all engines agree on every vector (D-0012)."""

from __future__ import annotations

import unittest

import _spec
import yaml


class DifferentialTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engines = _spec.load_engines()
        if len(self.engines) < 2:
            self.skipTest("fewer than two engines importable")

    def test_engines_agree(self) -> None:
        for document_path, _ in _spec.vector_pairs():
            document = yaml.safe_load(document_path.read_text())
            outcomes: dict[str, tuple[str, frozenset[str]]] = {}
            for engine_id, engine in self.engines.items():
                result = engine.validate(document)
                outcomes[engine_id] = (
                    result["status"],
                    frozenset(f["rule_id"] for f in result["findings"]),
                )
            with self.subTest(vector=document_path.stem):
                self.assertEqual(len(set(outcomes.values())), 1, outcomes)


if __name__ == "__main__":
    unittest.main()
