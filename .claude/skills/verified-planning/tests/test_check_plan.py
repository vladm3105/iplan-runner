import contextlib
import importlib.util
import io
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_plan.py"

# Load the gate in-process (no subprocess: faster, and avoids a security-linter
# flag for shelling out from a test).
_spec = importlib.util.spec_from_file_location("check_plan_under_test", SCRIPT)
_cp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cp)


class _Result:
    def __init__(self, returncode, stdout, stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run(*args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _cp.main([str(a) for a in args])
    return _Result(rc, buf.getvalue())


def _repo(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
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
GOOD_ROW = "| 1 | completion is logged | `task_completed` | src/loop.py:11 |\n"


def _plan(repo, ledger_rows, review=REVIEW_OK, name="PLAN-001_x.md"):
    p = repo / name
    p.write_text(LEDGER_HEADER + ledger_rows + "\n" + review)
    return p


def test_resolved_citation_passes(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW)
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


def test_line_out_of_range_with_symbol_warns(tmp_path):
    # PLAN-051: out-of-range line + symbol present elsewhere → warn (rc 0), the symbol is authoritative.
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x | `task_completed` | src/loop.py:999 |\n")
    r = _run(plan)
    assert r.returncode == 0, r.stdout
    assert "drifted" in r.stdout and "warn" in r.stdout


def test_drifted_symbol_warns(tmp_path):
    # PLAN-051: symbol present but not at the cited line → warn (rc 0), not a failure.
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x | `task_completed` | src/loop.py:1 |\n")
    r = _run(plan)
    assert r.returncode == 0, r.stdout
    assert "drifted" in r.stdout and "warn" in r.stdout  # the warn line is emitted


def test_symbol_genuinely_absent_fails(tmp_path):
    # A symbol that appears nowhere in the file is a real, still-failing error.
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x | `never_appears_anywhere` | src/loop.py:1 |\n")
    r = _run(plan)
    assert r.returncode == 1 and "not found in" in r.stdout


def test_no_symbol_out_of_range_fails(tmp_path):
    # No symbol to anchor on + out-of-range line → still an error (nothing to resolve against).
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x |  | src/loop.py:999 |\n")
    r = _run(plan)
    assert r.returncode == 1 and "out of range" in r.stdout


def test_no_symbol_in_range_passes(tmp_path):
    # No symbol + in-range line passes unchanged (the line is the only check).
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x |  | src/loop.py:5 |\n")
    r = _run(plan)
    assert r.returncode == 0, r.stdout


def test_fix_repoints_unambiguous_drift(tmp_path):
    # --fix re-points a drifted, single-occurrence citation, in place, per-row.
    repo = _repo(tmp_path)
    plan = _plan(repo, "| 1 | x | `task_completed` | src/loop.py:1 |\n")
    r = _run("--fix", plan)
    assert r.returncode == 0, r.stdout
    assert "re-pointed 1" in r.stdout
    assert "src/loop.py:11" in plan.read_text()  # 1 → 11, the real line
    r2 = _run(plan)  # now precise — no drift
    assert r2.returncode == 0 and "drifted" not in r2.stdout


def test_ambiguous_drift_warns_and_fix_leaves_it(tmp_path):
    # A symbol with multiple occurrences is ambiguous → warns, and --fix does NOT rewrite it.
    repo = _repo(tmp_path)
    (repo / "src" / "dup.py").write_text("\n".join(["x"] * 4 + ["dup_sym"] + ["x"] * 10 + ["dup_sym"]) + "\n")
    plan = _plan(repo, "| 1 | x | `dup_sym` | src/dup.py:1 |\n")
    before = plan.read_text()
    r = _run("--fix", plan)
    assert r.returncode == 0 and "re-pointed" not in r.stdout
    assert plan.read_text() == before  # unchanged
    r2 = _run(plan)
    assert r2.returncode == 0 and "drifted" in r2.stdout


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


REVIEW_SINGLE_ENTRY = "## Review log\n\n### Pass 1 - 2026-06-07\n- only one pass.\n"
REVIEW_NO_INDEP = (
    "## Review log\n\n### Pass 1 - 2026-06-07\n- self.\n\n### Pass 2 - 2026-06-07\n- self again, no new findings.\n"
)
REVIEW_NOT_GREEN = (
    "## Review log\n\n### Pass 1 - 2026-06-07\n- self.\n\n"
    "### Pass 2 - 2026-06-07 - independent\n- found a bug, unfixed.\n"
)


def test_fewer_than_two_passes_fails(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW, review=REVIEW_SINGLE_ENTRY)
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


# --- Improvement 1: robust green-final detection ---


def _review(final_line: str) -> str:
    return (
        f"## Review log\n\n### Pass 1 - 2026-06-07\n- self.\n\n### Pass 2 - 2026-06-07 - independent\n- {final_line}\n"
    )


def test_green_accepts_load_bearing_phrase(tmp_path):
    # the exact false-negative we hit: "no load-bearing findings" must pass
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW, review=_review("No load-bearing findings. Ready."))
    r = _run(plan)
    assert r.returncode == 0, r.stdout


def test_green_accepts_explicit_result_marker(tmp_path):
    # an explicit Result: ready marker passes even without a "findings" phrase
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW, review=_review("**Result:** ready"))
    r = _run(plan)
    assert r.returncode == 0, r.stdout


def test_green_still_rejects_open_finding(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW, review=_review("found an unfixed bug; not ready"))
    r = _run(plan)
    assert r.returncode == 1 and "zero-findings" in r.stdout


def test_green_does_not_falsematch_no_fix_for_findings(tmp_path):
    # the broadened matcher must NOT mark a pass with open findings green
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW, review=_review("no fix for these findings yet"))
    r = _run(plan)
    assert r.returncode == 1 and "zero-findings" in r.stdout


# --- Improvement 2: cross-repo citation support (--root) ---


def _cross_repo(tmp_path):
    # parent/repo (the plan's repo, has .git) + parent/sib (a sibling repo)
    repo = _repo(tmp_path / "repo")
    sib = tmp_path / "sib"
    sib.mkdir()
    (sib / "contract.yaml").write_text("kind: contract\n")
    plan = _plan(repo, "| 1 | sibling contract | `contract` | sib/contract.yaml:1 |\n")
    return plan


def test_cross_repo_citation_fails_without_root(tmp_path):
    plan = _cross_repo(tmp_path)  # repo_root=parent/repo; repo/sib does not exist
    r = _run(plan)
    assert r.returncode == 1 and "does not exist" in r.stdout


def test_cross_repo_citation_resolves_with_root(tmp_path):
    plan = _cross_repo(tmp_path)
    r = _run("--root", tmp_path, plan)  # parent/sib/contract.yaml resolves
    assert r.returncode == 0, r.stdout + r.stderr


# --- Improvement 3: positive output + --init ---


def test_success_prints_verified_count(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW)
    r = _run(plan)
    assert r.returncode == 0
    assert "verified 1" in r.stdout and "pass" in r.stdout


def test_init_scaffolds_sections(tmp_path):
    repo = _repo(tmp_path)
    p = repo / "PLAN-007_new.md"
    p.write_text("# New plan\n\nSome body.\n")
    r = _run("--init", p)
    assert r.returncode == 0
    text = p.read_text()
    assert "## Claim ledger" in text and "## Review log" in text


def test_init_is_idempotent(tmp_path):
    repo = _repo(tmp_path)
    plan = _plan(repo, GOOD_ROW)  # already has both sections
    before = plan.read_text()
    r = _run("--init", plan)
    assert r.returncode == 0
    assert plan.read_text() == before  # unchanged


def test_init_adds_ledger_without_duplicating_review(tmp_path):
    # plan has a Review log (with real passes) but no ledger → add ledger only,
    # keep the single existing Review log and its content
    repo = _repo(tmp_path)
    p = repo / "PLAN-008_x.md"
    p.write_text("# Plan\n\n" + REVIEW_OK)
    r = _run("--init", p)
    assert r.returncode == 0
    text = p.read_text()
    assert "## Claim ledger" in text
    assert text.count("## Review log") == 1  # not duplicated
    assert "no new findings" in text  # author's existing pass preserved


def test_init_adds_review_when_only_ledger(tmp_path):
    repo = _repo(tmp_path)
    p = repo / "PLAN-009_x.md"
    p.write_text(LEDGER_HEADER + GOOD_ROW)  # ledger, no review log
    r = _run("--init", p)
    assert r.returncode == 0
    text = p.read_text()
    assert "## Review log" in text
    assert text.count("## Claim ledger") == 1  # not duplicated
