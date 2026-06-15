"""Cross-engine conformance for the iplan-canonical-json signer (PLAN-014).

Every engine's ``security.iplanic_signing`` must reproduce Iplanic's vendored
golden vectors (``framework/remote/iplanic-vectors/``) byte-for-byte: the
canonical bytes, the ``sha256``, and the ``hmac-sha256``/``ed25519`` signature
``value``. The vectors are the shared contract with Iplanic.
"""

from __future__ import annotations

import importlib
import json
import unittest
from pathlib import Path

import _spec

VEC_DIR = _spec.FRAMEWORK / "remote" / "iplanic-vectors"


def _signers() -> dict[str, object]:
    signers: dict[str, object] = {}
    for entry in _spec.registry().get("engines", []):
        try:
            importlib.import_module(entry["package"])  # engine installed at all?
        except Exception:
            continue  # engine absent -> skip (consistent with the rest of the suite)
        # The base engine is present, so its iplan-canonical-json signer MUST import.
        # A missing rfc8785/cryptography dependency fails loudly here, never silently.
        signers[entry["id"]] = importlib.import_module(f"{entry['package']}.security.iplanic_signing")
    return signers


def _vectors() -> list[Path]:
    return sorted(VEC_DIR.glob("*.json"))


class IplanicSigningConformanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.signers = _signers()
        if not self.signers:
            self.skipTest("no engines importable")

    def test_reproduces_iplanic_vectors(self) -> None:
        vectors = _vectors()
        self.assertTrue(vectors, "no vendored Iplanic vectors found")
        for engine_id, ic in self.signers.items():
            for path in vectors:
                v = json.loads(path.read_text())
                with self.subTest(engine=engine_id, vector=path.stem):
                    self._check(ic, path.stem, v)

    def _check(self, ic: object, name: str, v: dict) -> None:
        if name.startswith("canon_"):
            self.assertEqual(ic.canonicalize(v["input"]), v["canonical"].encode("utf-8"))
            self.assertEqual(ic.canonical_hash(v["input"]), v["sha256"])
        elif name == "normalize_omit_vs_null":
            self.assertEqual(ic.canonical_hash(v["input_omit"]), ic.canonical_hash(v["input_null"]))
            self.assertEqual(ic.canonical_hash(v["input_omit"]), v["sha256"])
        elif name == "sig_hmac":
            payload = ic.signing_payload(v["event"])
            value = ic.sign(payload, algorithm="hmac-sha256", key=bytes.fromhex(v["key_hex"]))
            self.assertEqual(value, v["value"])
            self.assertTrue(ic.verify(payload, value, algorithm="hmac-sha256", key=bytes.fromhex(v["key_hex"])))
        elif name == "sig_ed25519":
            payload = ic.signing_payload(v["event"])
            value = ic.sign(payload, algorithm="ed25519", key=bytes.fromhex(v["ed25519_seed_hex"]))
            self.assertEqual(value, v["value"])
            self.assertTrue(ic.verify(payload, value, algorithm="ed25519", key=bytes.fromhex(v["ed25519_public_hex"])))
        elif name == "seal_hash":
            seal = ic.canonical_hash({"payload": v["payload"], "evidence_manifest": v["evidence_manifest"]})
            self.assertEqual(seal, v["sha256"])
        else:  # pragma: no cover - guard against an unhandled vendored vector
            self.fail(f"unhandled vendored vector: {name}")


if __name__ == "__main__":
    unittest.main()
