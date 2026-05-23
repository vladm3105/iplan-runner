"""Engine spec parity + strict isolation (no cross-engine imports)."""
from __future__ import annotations

import unittest

import _spec


class EngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engines = _spec.registry()["engines"]

    def test_framework_spec_version_parity(self) -> None:
        expected = _spec.framework_version()
        for engine in self.engines:
            with self.subTest(engine=engine["id"]):
                marker = _spec.REPO_ROOT / engine["path"] / "FRAMEWORK_SPEC_VERSION"
                self.assertTrue(marker.is_file())
                self.assertEqual(marker.read_text().strip(), expected)

    def test_strict_isolation(self) -> None:
        packages = {e["id"]: e["package"] for e in self.engines}
        for engine in self.engines:
            others = [pkg for eid, pkg in packages.items() if eid != engine["id"]]
            src = _spec.REPO_ROOT / engine["path"] / "src"
            for py_file in src.glob("**/*.py"):
                text = py_file.read_text()
                for other_pkg in others:
                    with self.subTest(engine=engine["id"], file=py_file.name, other=other_pkg):
                        self.assertNotIn(other_pkg, text)


if __name__ == "__main__":
    unittest.main()
