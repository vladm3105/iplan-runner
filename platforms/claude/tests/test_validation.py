"""Replay the golden vectors through the Hermes engine."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from iops_claude import ClaudeEngine

ROOT = Path(__file__).resolve().parents[3]
VECTORS = ROOT / "framework" / "conformance" / "vectors"


def _cases() -> list[tuple[str, Path]]:
    cases = []
    for expect in sorted(VECTORS.glob("**/*.expect.yaml")):
        cases.append((expect.stem.replace(".expect", ""), expect))
    return cases


@pytest.mark.parametrize("name,expect_path", _cases(), ids=lambda c: c if isinstance(c, str) else "")
def test_vector(name: str, expect_path: Path) -> None:
    expected = yaml.safe_load(expect_path.read_text())
    document = yaml.safe_load(expect_path.with_name(expect_path.name.replace(".expect.yaml", ".yaml")).read_text())
    result = ClaudeEngine().validate(document)
    assert result["status"] == expected["status"], name
    assert {f["rule_id"] for f in result["findings"]} == set(expected.get("rule_ids") or []), name
