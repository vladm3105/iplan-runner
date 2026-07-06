"""Non-gated unit coverage for the PLAN-022 repo→workspace clone + executor seam (runs in CI).

Exercises `provision_workspace` (clone-vs-passthrough + `_slug` path-safety) and the `execute` wiring
(clone happens, and the injected `make_executor` receives the cloned workspace) against a **local**
`file://` fixture repo — no network. The full HTTP wire stays the gated `test_task_receiver.py`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from iplan_claude.engine import ClaudeEngine
from iplan_claude.receiver import ReceiverDeps, execute
from iplan_claude.receiver.service import provision_workspace
from iplan_claude.relay import store
from iplan_claude.relay.client import Response
from iplan_claude.vcs.git import commit_all


def _source_repo(path: Path, content: str = "hi\n") -> str:
    """git-init a fixture repo with one commit on `main`; return its `file://` URL."""
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "a.txt").write_text(content)
    commit_all(path, "main", "c1")
    return path.as_uri()


def _payload(url: str, *, run_id: str = "R1", task_id: str = "T1", base_ref: str = "main") -> dict[str, Any]:
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
        "context_package": {
            "repository": {"url": url, "default_branch": "main", "base_ref": base_ref},
            "forbidden_paths": [".git"],
        },
    }


def test_provision_clones_object_repo(tmp_path: Path) -> None:
    url = _source_repo(tmp_path / "src")
    root = tmp_path / "ws"
    ws = provision_workspace(_payload(url), str(root), run_id="R1", task_id="T1")
    assert ws == str(root / "R1" / "T1")  # per-run dir under the root
    assert (Path(ws) / "a.txt").read_text() == "hi\n"  # cloned + checked out at base_ref


def test_provision_passthrough_string_repository(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    payload = {"context_package": {"repository": "."}}  # file-intake shape → no clone
    assert provision_workspace(payload, str(root), run_id="R1", task_id="T1") == str(root)


def test_provision_passthrough_absent_repository(tmp_path: Path) -> None:
    assert provision_workspace({}, str(tmp_path), run_id="R1", task_id="T1") == str(tmp_path)


def test_provision_slug_blocks_path_traversal(tmp_path: Path) -> None:
    url = _source_repo(tmp_path / "src")
    root = tmp_path / "ws"
    ws = provision_workspace(_payload(url, task_id="../../etc"), str(root), run_id="R1", task_id="../../etc")
    resolved = Path(ws).resolve()
    assert root.resolve() in resolved.parents  # a "../" task_id cannot escape the workspace root
    assert ".." not in Path(ws).parts


def test_provision_rejects_empty_slugging_id(tmp_path: Path) -> None:
    url = _source_repo(tmp_path / "src")
    with pytest.raises(ValueError):  # a task_id that sanitizes to "." / ".." / "" fails, never escapes
        provision_workspace(_payload(url, task_id=".."), str(tmp_path / "ws"), run_id="R1", task_id="..")


class _FakeClient:
    """Records delivered events; accepts every one (stands in for iplanic `/v1/events`)."""

    def __init__(self) -> None:
        self.delivered: list[dict[str, Any]] = []

    def deliver(self, event: dict[str, Any]) -> Response:
        self.delivered.append(event)
        return Response(status=202, body={})


def test_execute_clones_and_hands_the_workspace_to_the_executor(tmp_path: Path) -> None:
    url = _source_repo(tmp_path / "src")
    root = tmp_path / "ws"
    store_dir = str(tmp_path / "store")
    seen: dict[str, str] = {}

    def spy(engine: ClaudeEngine, workspace: str) -> Any:
        seen["workspace"] = workspace
        return engine.default_executor()  # the deterministic Mock still produces the events

    store.accept_task(store_dir, "R1", "T1")  # the door normally does this before scheduling execute
    deps = ReceiverDeps(
        engine=ClaudeEngine(),
        store_dir=store_dir,
        workspace=str(root),
        client=_FakeClient(),
        key=b"k",
        key_id="k1",
        make_executor=spy,
    )
    execute(_payload(url), deps)

    assert seen["workspace"] == str(root / "R1" / "T1")  # the executor got the CLONED path, not the root
    assert (Path(seen["workspace"]) / "a.txt").read_text() == "hi\n"
    assert store.task_status(store_dir, "R1", "T1") == "done"  # ran + drained + settled ok


def test_execute_bad_repo_settles_failed_without_crashing(tmp_path: Path) -> None:
    store_dir = str(tmp_path / "store")
    store.accept_task(store_dir, "R1", "T1")
    bad = _payload((tmp_path / "nope").as_uri())  # a non-existent repo → clone raises
    deps = ReceiverDeps(
        engine=ClaudeEngine(),
        store_dir=store_dir,
        workspace=str(tmp_path / "ws"),
        client=_FakeClient(),
        key=b"k",
        key_id="k1",
    )
    execute(bad, deps)  # must not raise (the worker thread never crashes)
    assert store.task_status(store_dir, "R1", "T1") == "failed"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
