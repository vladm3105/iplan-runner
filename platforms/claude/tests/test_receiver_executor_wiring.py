"""Non-gated unit coverage for the config-selected receiver executor (PLAN-023, runs in CI).

`receiver.executor` picks the receiver's executor via the PLAN-022 `make_executor` seam: `mock` (default)
or `host` (the real `HostRuntimeExecutor` governor over a `StubRuntimeClient` — the real Claude Code hook
is a PLAN-024 swap). Covers the config load, the `_executor_factory` selection + fail-loud, and an
`execute` end-to-end through the `host` governor against a local `file://` fixture repo (no network).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from iplan_claude.cli.commands import _executor_factory
from iplan_claude.config import load_config
from iplan_claude.engine import ClaudeEngine
from iplan_claude.executor.hostruntime import HostRuntimeExecutor
from iplan_claude.executor.mock import MockExecutor
from iplan_claude.receiver import ReceiverDeps, execute
from iplan_claude.relay import store
from iplan_claude.relay.client import Response
from iplan_claude.vcs.git import commit_all


def test_config_default_executor_is_mock(tmp_path: Path) -> None:
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text("receiver:\n  enabled: true\n")  # no executor key
    assert load_config(str(cfg_path)).receiver_executor == "mock"


def test_config_reads_receiver_executor(tmp_path: Path) -> None:
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text("receiver:\n  enabled: true\n  executor: host\n")
    assert load_config(str(cfg_path)).receiver_executor == "host"


def test_executor_factory_selects_by_mode() -> None:
    engine = ClaudeEngine()
    assert isinstance(_executor_factory("mock")(engine, "/ws"), MockExecutor)
    host = _executor_factory("host")(engine, "/ws")
    assert isinstance(host, HostRuntimeExecutor)


def test_executor_factory_unknown_mode_raises() -> None:
    with pytest.raises(ValueError):  # the CLI turns this into an error + non-zero exit
        _executor_factory("bogus")


def _source_repo(path: Path) -> str:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "a.txt").write_text("hi\n")
    commit_all(path, "main", "c1")
    return path.as_uri()


def _payload(url: str, *, run_id: str = "R1", task_id: str = "T1") -> dict[str, Any]:
    return {
        "iplan_id": "IPLAN-01",
        "plan_version_id": "PV-01",
        "org_id": "org-a",
        "project_id": "proj-1",
        "run_id": run_id,
        "step_id": "STEP-001",
        "task_id": task_id,
        "executor_id": "exec:iopsremote2zqf7kx3a",
        "work_order": {
            "work_order_id": "WORK-1",
            "todos": [{"todo_id": "TODO-1", "description": "d", "acceptance_criteria": ["ok"]}],
        },
        "context_package": {"repository": {"url": url, "default_branch": "main", "base_ref": "main"}},
    }


class _FakeClient:
    def __init__(self) -> None:
        self.delivered: list[dict[str, Any]] = []

    def deliver(self, event: dict[str, Any]) -> Response:
        self.delivered.append(event)
        return Response(status=202, body={})


def test_execute_runs_the_host_governor_and_settles_done(tmp_path: Path) -> None:
    url = _source_repo(tmp_path / "src")
    store_dir = str(tmp_path / "store")
    store.accept_task(store_dir, "R1", "T1")
    deps = ReceiverDeps(
        engine=ClaudeEngine(),
        store_dir=store_dir,
        workspace=str(tmp_path / "ws"),
        client=_FakeClient(),
        key=b"k",
        key_id="k1",
        make_executor=_executor_factory("host"),  # HostRuntimeExecutor(StubRuntimeClient)
    )
    execute(_payload(url), deps)
    # the run went through the real governor (StubRuntimeClient → success, empty scope) and settled ok
    assert store.task_status(store_dir, "R1", "T1") == "done"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
