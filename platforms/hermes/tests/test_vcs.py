"""Landing / VCS: commit_all, land, gate-requires-commit (Hermes)."""

from __future__ import annotations

import itertools
import subprocess
from collections.abc import Callable
from pathlib import Path

from iplan_hermes import HermesEngine
from iplan_hermes.executor.base import IdSource
from iplan_hermes.vcs.git import clone, commit_all, current_branch, has_changes, head_sha

EV = {"kind": "test", "summary": "ok", "location": "ci://1"}
MANIFEST = {
    "metadata": {"schema_version": "1.0", "document_type": "iplan-intake", "framework": "iops"},
    "intake_control": {
        "source_iplan": "IPLAN-001",
        "source_iplan_version": "1.0.0",
        "source_iplan_checksum": "sha256:" + "a" * 64,
        "exec_ready_score": 92,
        "approved": True,
    },
    "isolation_scope": {"client_id": "c", "project_id": "p", "allowed_roots": ["src/"]},
    "task_graph": [{"task_id": "T1", "title": "a", "depends_on": [], "acceptance": {"criteria": ["x"]}}],
}


def _clock() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"2026-05-24T10:{next(counter):02d}:00Z"


def _noop_sleep(_seconds: float) -> None:
    return None


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def test_not_committed_rule_via_vectors() -> None:
    import yaml

    root = Path(__file__).resolve().parents[3] / "framework/conformance/vectors/ledger"
    engine = HermesEngine()
    committed = yaml.safe_load((root / "committed.yaml").read_text())
    not_committed = yaml.safe_load((root / "not_committed.yaml").read_text())
    assert engine.validate(committed)["status"] == "pass"
    result = engine.validate(not_committed)
    assert {f["rule_id"] for f in result["findings"]} == {"LEDGER.NOT_COMMITTED"}


def test_commit_all(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x\n")
    assert has_changes(tmp_path) is True
    sha = commit_all(tmp_path, "iops/x", "first")
    assert len(sha) >= 7
    assert has_changes(tmp_path) is False
    assert current_branch(tmp_path) == "iops/x"


def test_land_records_commit(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    engine = HermesEngine()
    spec = {
        "T1": {
            "actions": [{"type": "write", "path": "src/a.py", "content": "x\n"}],
            "checks": [{"name": "ok", "command": ["python", "-c", "import sys; sys.exit(0)"]}],
        }
    }
    run_result = engine.run(
        MANIFEST, engine.scripted_executor(spec, tmp_path), clock=_clock(), ids=IdSource(), sleep=_noop_sleep
    )
    assert run_result.gate_result["status"] == "passed"

    landed = engine.land(run_result.ledger, str(tmp_path), branch="iops/x", clock=_clock())
    assert landed.ledger["ledger_control"]["requires_landing"] is True
    assert landed.ledger["vcs"]["commits"]
    assert landed.gate_result["status"] == "passed"
    assert any(e["event_type"] == "commit" for e in landed.ledger["execution_log"])
    receipt = engine.build_handover(landed.ledger, landed.gate_result)
    assert receipt["handover_control"]["commit"]["branch"] == "iops/x"
    assert receipt["result"]["status"] == "completed"


def test_land_noop_on_clean_tree(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n")
    commit_all(tmp_path, "main", "seed")  # clean tree now
    engine = HermesEngine()
    ledger = {
        "metadata": {"document_type": "iplan-ledger"},
        "ledger_control": {"ledger_id": "L", "requires_landing": False},
        "isolation_scope": {"client_id": "c", "project_id": "p", "allowed_roots": ["src/"]},
        "task_ledger": [],
        "execution_log": [],
        "vcs": {"branch": "main", "commits": []},
    }
    landed = engine.land(ledger, str(tmp_path), branch="iops/x", clock=_clock())
    assert landed.ledger["ledger_control"]["requires_landing"] is False
    assert landed.ledger["vcs"]["commits"] == []


def _source_repo(path: Path) -> tuple[str, str, str, str]:
    """Build a fixture source repo with two commits on `main` + a `v1` tag at the first.
    Returns (file_url, sha1, sha2, tag)."""
    _init_repo(path)
    (path / "a.txt").write_text("v1\n")
    sha1 = commit_all(path, "main", "c1")
    (path / "a.txt").write_text("v2\n")
    sha2 = commit_all(path, "main", "c2")
    subprocess.run(["git", "-C", str(path), "tag", "v1", sha1], check=True)
    return path.as_uri(), sha1, sha2, "v1"


def test_clone_checks_out_branch_tag_and_sha(tmp_path: Path) -> None:
    url, sha1, sha2, tag = _source_repo(tmp_path / "src")

    d_branch = tmp_path / "cb"
    assert clone(url, "main", d_branch) == sha2  # branch → tip SHA
    assert (d_branch / "a.txt").read_text() == "v2\n"
    assert head_sha(d_branch) == sha2

    d_tag = tmp_path / "ct"
    assert clone(url, tag, d_tag) == sha1  # tag → first commit
    assert (d_tag / "a.txt").read_text() == "v1\n"

    d_sha = tmp_path / "cs"
    assert clone(url, sha1, d_sha) == sha1  # arbitrary SHA (needs the full, non-shallow clone)
    assert (d_sha / "a.txt").read_text() == "v1\n"


def test_clone_bad_url_raises(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(subprocess.CalledProcessError):  # a bad coordinate surfaces (receiver catches it)
        clone((tmp_path / "does-not-exist").as_uri(), "main", tmp_path / "dst")


def test_clone_sink_guard_refuses_remote_helper_and_dash(tmp_path: Path) -> None:
    import pytest

    # B1 sink guard: clone() itself refuses the `ext::` remote-helper (RCE) and a
    # leading-dash url, independent of the door's allow-list — never reaching git.
    for bad in ("ext::sh -c touch /tmp/pwned", "-oProxyCommand=evil"):
        with pytest.raises(ValueError):
            clone(bad, "main", tmp_path / "dst")
