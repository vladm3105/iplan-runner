"""GA acceptance: the full pipeline reaches committed + green + monitored + signed.

Offline and deterministic — real edits + checks via the ScriptedExecutor in a tmp
git workspace, an injected clock/ids, and a test signing key. No network. This is
the per-engine GA proof (not a conformance vector); cross-engine parity is already
covered by the scenario/chain/decision differentials.
"""

from __future__ import annotations

import itertools
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from iplan_claude import ClaudeEngine
from iplan_claude.executor.base import IdSource
from iplan_claude.monitoring.telemetry import emit_run_telemetry

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"


def _clock() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"2026-05-27T10:{next(counter):02d}:00Z"


def _noop_sleep(_seconds: float) -> None:
    return None


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)  # noqa: S603,S607


class _RecordingProvider:
    """Captures self-telemetry metrics so we can assert the run was observed."""

    def __init__(self) -> None:
        self.metrics: dict[str, float] = {}

    def start_span(self, name: str, attributes: dict[str, Any]) -> None:
        return None

    def record_metric(self, name: str, value: float) -> None:
        self.metrics[name] = value

    def log(self, name: str, severity: str, body: str) -> None:
        return None


def test_acceptance_end_to_end(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    engine = ClaudeEngine()
    engine._config.signing_key = "ga-acceptance-key"  # pragma: allowlist secret

    # 1. Intake: normalize + validate the SDD-IPLAN.
    manifest = engine.ingest_iplan(EXAMPLES / "IPLAN-EXAMPLE.yaml")
    assert engine.validate(manifest)["status"] == "pass"

    # 2. Run: real edits + passing checks -> green + reconciled.
    actions = yaml.safe_load((EXAMPLES / "actions.yaml").read_text())
    run_result = engine.run(
        manifest,
        engine.scripted_executor(actions, tmp_path),
        clock=_clock(),
        ids=IdSource(),
        sleep=_noop_sleep,
    )
    assert run_result.gate_result["status"] == "passed"
    assert run_result.ledger["reconciliation"]["allowed"] is True
    assert [t["status"] for t in run_result.ledger["task_ledger"]] == ["completed", "completed"]
    assert (tmp_path / "src" / "greeting.py").exists()

    # 3. Land: real commit recorded + signed (operator-authorized).
    landed = engine.land(
        run_result.ledger,
        str(tmp_path),
        branch="iops/example",
        actor={"id": "op", "role": "operator"},
        clock=_clock(),
    )
    assert landed.ledger["vcs"]["commits"]
    assert any(e["event_type"] == "commit" for e in landed.ledger["execution_log"])
    assert engine.verify_ledger(landed.ledger) is True

    # 4. Handover: completed, with the commit recorded.
    receipt = engine.build_handover(landed.ledger, landed.gate_result)
    assert receipt["result"]["status"] == "completed"
    assert receipt["handover_control"]["commit"]["branch"] == "iops/example"

    # 5. Monitor: manifest valid; healthy samples -> no alerts; breach -> alert.
    monitoring = yaml.safe_load((EXAMPLES / "monitoring.yaml").read_text())
    assert engine.validate(monitoring)["status"] == "pass"
    assert engine.evaluate_alerts(monitoring, {"availability_ratio": 99.95}) == []
    breach = engine.evaluate_alerts(monitoring, {"availability_ratio": 90.0})
    assert [a["alert_id"] for a in breach] == ["ALERT-001"]

    # Self-telemetry: the run's own signals are recorded.
    provider = _RecordingProvider()
    emit_run_telemetry(provider, landed.ledger)
    assert provider.metrics["iplan.tasks.completed"] == 2.0
    assert provider.metrics["iplan.tasks.blocked"] == 0.0
