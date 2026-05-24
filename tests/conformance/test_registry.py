"""Registry integrity + spec-version parity."""
from __future__ import annotations

import unittest

import _spec


class RegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = _spec.registry()

    def test_spec_version_matches_framework(self) -> None:
        self.assertEqual(
            self.reg["metadata"]["spec_version"], _spec.framework_version()
        )

    def test_artifact_ids_unique(self) -> None:
        ids = [a["id"] for a in self.reg["artifacts"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_error_prefixes_unique(self) -> None:
        prefixes = [a["error_prefix"] for a in self.reg["artifacts"] if "error_prefix" in a]
        self.assertEqual(len(prefixes), len(set(prefixes)))

    def test_referenced_paths_exist(self) -> None:
        paths = [a["template"] for a in self.reg["artifacts"]]
        paths += list(self.reg["protocol_docs"])
        paths += [
            self.reg["rule_catalog"],
            self.reg["vectors_root"],
            self.reg["intake_samples_root"],
            self.reg["scenarios_root"],
            self.reg["sandbox_root"],
            self.reg["leases_root"],
            self.reg["signing_root"],
            self.reg["authz_root"],
            self.reg["budget_root"],
            self.reg["alert_root"],
        ]
        for rel in paths:
            with self.subTest(path=rel):
                self.assertTrue((_spec.REPO_ROOT / rel).exists(), rel)

    def test_engine_paths_exist(self) -> None:
        for engine in self.reg["engines"]:
            with self.subTest(engine=engine["id"]):
                self.assertTrue((_spec.REPO_ROOT / engine["path"]).is_dir())


if __name__ == "__main__":
    unittest.main()
