import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_plan.py"


def _run(plan: Path):
    return subprocess.run([sys.executable, str(SCRIPT), str(plan)], capture_output=True, text=True)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    src = tmp_path / "src"
    src.mkdir()
    (src / "loop.py").write_text(
        "\n".join(f"line{n}" for n in range(1, 11)) + "\nappend_event(task_completed)\n"
    )  # line 11
    return tmp_path


LEDGER_HEADER = "## Claim ledger\n\n| # | Claim | Symbol | Citation |\n|---|---|---|---|\n"
REVIEW_OK = (
    "## Review log\n\n"
    "### Pass 1 - 2026-06-07\n- self review.\n\n"
    "### Pass 2 - 2026-06-07 - independent\n- no new findings.\n"
)


def _plan(repo, ledger_rows, review=REVIEW_OK):
    p = repo / "PLAN-001_x.md"
    p.write_text(LEDGER_HEADER + ledger_rows + "\n" + review)
    return p


def test_resolved_citation_passes(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | completion is logged | `task_completed` | src/loop.py:11 |\n")
    r = _run(plan)
    assert r.returncode == 0, r.stdout + r.stderr


def test_missing_file_fails(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x | `foo` | src/nope.py:3 |\n")
    r = _run(plan)
    assert r.returncode == 1
    assert "does not exist" in r.stdout


def test_directory_citation_fails_gracefully(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x | `src` | src:1 |\n")
    r = _run(plan)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "is not a file" in r.stdout
    assert "Traceback" not in r.stderr


def test_line_out_of_range_fails(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x | `task_completed` | src/loop.py:999 |\n")
    r = _run(plan)
    assert r.returncode == 1 and "out of range" in r.stdout


def test_symbol_not_near_line_fails(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x | `task_completed` | src/loop.py:1 |\n")
    r = _run(plan)
    assert r.returncode == 1 and "not found within" in r.stdout


def test_unverified_row_fails(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x | `foo` | UNVERIFIED |\n")
    r = _run(plan)
    assert r.returncode == 1 and "UNVERIFIED" in r.stdout


def test_empty_ledger_fails(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, "")
    r = _run(plan)
    assert r.returncode == 1 and "no rows" in r.stdout


REVIEW_ONE_PASS = "## Review log\n\n### Pass 1 - 2026-06-07\n- only one pass.\n"
REVIEW_NO_INDEP = (
    "## Review log\n\n### Pass 1 - 2026-06-07\n- self.\n\n### Pass 2 - 2026-06-07\n- self again, no new findings.\n"
)
REVIEW_NOT_GREEN = (
    "## Review log\n\n### Pass 1 - 2026-06-07\n- self.\n\n"
    "### Pass 2 - 2026-06-07 - independent\n- found a bug, unfixed.\n"
)
GOOD_ROW = "| 1 | completion is logged | `task_completed` | src/loop.py:11 |\n"


def test_fewer_than_two_passes_fails(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW, review=REVIEW_ONE_PASS)
    r = _run(plan)
    assert r.returncode == 1 and "at least two" in r.stdout


def test_no_independent_pass_fails(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW, review=REVIEW_NO_INDEP)
    r = _run(plan)
    assert r.returncode == 1 and "independent" in r.stdout


def test_final_pass_not_green_fails(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW, review=REVIEW_NOT_GREEN)
    r = _run(plan)
    assert r.returncode == 1 and "zero-findings" in r.stdout


def test_full_valid_plan_passes(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW)
    r = _run(plan)
    assert r.returncode == 0, r.stdout


def test_non_plan_markdown_skipped(tmp_path):
    repo = _repo(tmp_path)
    p = repo / "PLAN-README.md"
    p.write_text("# just notes\n\nNo ledger, no review log here.\n")
    r = _run(p)
    assert r.returncode == 0 and "ok" in r.stdout


def test_missing_review_when_ledger_present_fails(tmp_path):
    repo = _repo(tmp_path)
    p = repo / "PLAN-002.md"
    p.write_text(LEDGER_HEADER + GOOD_ROW)
    r = _run(p)
    assert r.returncode == 1 and "Review log" in r.stdout
