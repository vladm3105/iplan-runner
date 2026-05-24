"""Reader parity: every engine normalizes the same IPLAN identically (D-0012)."""
from __future__ import annotations

import unittest

import _spec


class IntakeReaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engines = _spec.load_engines()
        if not self.engines:
            self.skipTest("no engines importable")
        self.samples_root = _spec.REPO_ROOT / _spec.registry()["intake_samples_root"]

    def test_reader_parity_and_validity(self) -> None:
        samples = sorted(self.samples_root.glob("*/iplan.yaml"))
        self.assertTrue(samples, "no intake samples found")
        for sample in samples:
            manifests = []
            for engine_id, engine in self.engines.items():
                manifest = engine.ingest_iplan(str(sample))
                with self.subTest(engine=engine_id, sample=sample.parent.name):
                    self.assertEqual(engine.validate(manifest)["status"], "pass")
                manifests.append(manifest)
            with self.subTest(sample=sample.parent.name):
                for other in manifests[1:]:
                    self.assertEqual(other, manifests[0])


if __name__ == "__main__":
    unittest.main()
