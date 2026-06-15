"""Cross-engine Iplanic remote-executor conformance (framework/conformance/remote).

For each remote sample x engine: the payload->manifest projection and the
ledger->execution-event projection match the golden expect, every emitted event
carries exactly the vendored required fields (`signature` exactly its three keys),
the payload validator emits the expected REMOTE.* rule_ids, and both engines agree
(differential).
"""

from __future__ import annotations

import importlib
import unittest

import _spec
import yaml

REMOTE = _spec.FRAMEWORK / "conformance" / "remote"
REQUIRED = set(yaml.safe_load((_spec.FRAMEWORK / "remote" / "EXECUTION-EVENT-TEMPLATE.yaml").read_text())["required"])
KEY = b"conformance-key"
KEY_ID = "key-1"


def _engine_packages() -> dict[str, str]:
    packages: dict[str, str] = {}
    for entry in _spec.registry().get("engines", []):
        try:
            importlib.import_module(entry["package"])
        except Exception:
            continue
        packages[entry["id"]] = entry["package"]
    return packages


class RemoteConformanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engines = _engine_packages()
        if not self.engines:
            self.skipTest("no engines importable")

    def test_accept_projection_matches_golden_and_is_cross_engine_identical(self) -> None:
        case = REMOTE / "accept"
        payload = yaml.safe_load((case / "payload.yaml").read_text())
        ledger = yaml.safe_load((case / "ledger.yaml").read_text())
        expect = yaml.safe_load((case / "expect.yaml").read_text())
        manifests, eventsets = [], []
        for engine_id, pkg in self.engines.items():
            payload_mod = importlib.import_module(f"{pkg}.intake.payload")
            events_mod = importlib.import_module(f"{pkg}.ledger.events")
            manifest = payload_mod.ingest_task_payload(str(case / "payload.yaml"))
            events = events_mod.to_execution_events(ledger, payload, key=KEY, key_id=KEY_ID)
            with self.subTest(engine=engine_id):
                self.assertEqual(manifest, expect["manifest"])
                self.assertEqual(events, expect["events"])
                for event in events:
                    self.assertEqual(REQUIRED - set(event), set())
                    self.assertEqual(set(event["signature"]), {"key_id", "algorithm", "value"})
            manifests.append(manifest)
            eventsets.append(events)
        if len(self.engines) >= 2:
            self.assertEqual(manifests[0], manifests[1])
            self.assertEqual(eventsets[0], eventsets[1])

    def test_reject_payload_emits_expected_rules(self) -> None:
        cases = sorted(p.parent for p in REMOTE.glob("reject_*/expect.yaml"))
        self.assertTrue(cases, "no reject_* conformance vectors found")
        for case in cases:
            payload = yaml.safe_load((case / "payload.yaml").read_text())
            expect = yaml.safe_load((case / "expect.yaml").read_text())
            for engine_id, pkg in self.engines.items():
                rules_mod = importlib.import_module(f"{pkg}.validation.payload_rules")
                findings = rules_mod.validate_payload(payload)
                with self.subTest(case=case.name, engine=engine_id):
                    self.assertEqual(sorted(f.rule_id for f in findings), expect["rule_ids"])


if __name__ == "__main__":
    unittest.main()
