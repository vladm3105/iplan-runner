"""Contract artifacts parse and match the registry."""
from __future__ import annotations

import unittest

import _spec


class ContractTest(unittest.TestCase):
    def test_artifacts_parse_and_match(self) -> None:
        for artifact in _spec.registry()["artifacts"]:
            with self.subTest(artifact=artifact["id"]):
                doc = _spec.load_yaml(artifact["template"])
                self.assertIsInstance(doc, dict)
                self.assertEqual(
                    doc.get("metadata", {}).get("document_type"),
                    artifact["document_type"],
                )

    def test_protocol_docs_exist(self) -> None:
        for rel in _spec.registry()["protocol_docs"]:
            with self.subTest(doc=rel):
                self.assertTrue((_spec.REPO_ROOT / rel).is_file(), rel)


if __name__ == "__main__":
    unittest.main()
