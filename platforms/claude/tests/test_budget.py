"""Budget decisions + config loading (Claude)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from iops_claude.budget import Budget, check
from iops_claude.config import load_config, secrets_from_env

ROOT = Path(__file__).resolve().parents[3]
BUDGET = ROOT / "framework/conformance/budget"


@pytest.mark.parametrize("case", sorted(p.name for p in BUDGET.iterdir()))
def test_budget_matches_vectors(case: str) -> None:
    inp = yaml.safe_load((BUDGET / case / "input.yaml").read_text())
    expect = yaml.safe_load((BUDGET / case / "expect.yaml").read_text())
    assert check(inp["budget"], inp["usage"]) == expect


def test_budget_dataclass() -> None:
    assert check(Budget(max_tokens=10), {"tokens": 20})["reason"] == "BUDGET.TOKENS_EXCEEDED"
    assert check(Budget(), {"tokens": 10_000})["allowed"] is True


def test_load_config_file_and_env_secrets(tmp_path: Path) -> None:
    cfg_file = tmp_path / "iops.yaml"
    cfg_file.write_text("exec_ready_min: 95\nmax_retries: 3\nsigning_key: SHOULD_BE_IGNORED\n")
    env = {"IOPS_SECRET_A": "topsecret", "IOPS_SIGNING_KEY": "from-env"}
    cfg = load_config(cfg_file, env=env)
    assert cfg.exec_ready_min == 95
    assert cfg.max_retries == 3
    assert cfg.secrets == ["topsecret"]
    assert cfg.signing_key == "from-env"  # from env, never the file


def test_secrets_from_env() -> None:
    assert secrets_from_env(env={"IOPS_SECRET_X": "s1", "OTHER": "n"}) == ["s1"]
