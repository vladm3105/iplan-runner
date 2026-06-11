"""Rule catalog is well-formed and fully covered by vectors (both directions)."""

from __future__ import annotations

import unittest

import _spec
import yaml


class RuleCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = _spec.rule_catalog()
        self.ids = {r["id"] for r in self.catalog["rules"]}
        self.severities = set(self.catalog["severities"])

    def test_well_formed(self) -> None:
        seen: set[str] = set()
        categories = set(self.catalog["categories"])
        for rule in self.catalog["rules"]:
            with self.subTest(rule=rule["id"]):
                self.assertNotIn(rule["id"], seen)
                seen.add(rule["id"])
                self.assertIn(rule["category"], categories)
                self.assertIn(rule["severity"], self.severities)

    def _vector_rule_ids(self) -> set[str]:
        used: set[str] = set()
        for _, expect in _spec.vector_pairs():
            data = yaml.safe_load(expect.read_text())
            used.update(data.get("rule_ids") or [])
        # Remote-executor conformance expects (REMOTE-001) live under remote_root.
        for expect in (_spec.FRAMEWORK / "conformance" / "remote").glob("**/expect.yaml"):
            used.update((yaml.safe_load(expect.read_text()) or {}).get("rule_ids") or [])
        return used

    def test_every_rule_has_a_vector(self) -> None:
        self.assertEqual(self.ids - self._vector_rule_ids(), set())

    def test_every_vector_rule_in_catalog(self) -> None:
        self.assertEqual(self._vector_rule_ids() - self.ids, set())


if __name__ == "__main__":
    unittest.main()
