#!/usr/bin/env python3
"""Gate a PLAN-*.md: Claim-ledger citations must resolve; Review log must be structured.

stdlib only. Exit 0 = ok, 1 = failures (reported on stdout), 2 = usage error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CITATION_RE = re.compile(r"([\w./\-]+):(\d+)(?:-(\d+))?")
PROXIMITY = 3  # lines; tunable window for the symbol check
PASS_RE = re.compile(r"^###\s+Pass\s+(\d+)\b(.*)$", re.MULTILINE)
ZERO_FINDINGS_RE = re.compile(
    r"no (new |further )?findings|findings:\s*none|finds nothing|nothing (new|further)|zero .*findings",
    re.IGNORECASE,
)


def repo_root(start: Path) -> Path:
    p = start.resolve()
    for d in (p, *p.parents):
        if (d / ".git").exists():
            return d
    return Path.cwd()


def sections(text: str) -> dict[str, str]:
    """Map level-2 header (lowercased, trimmed) -> body up to the next level-2 header."""
    out: dict[str, str] = {}
    cur = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"##\s+(.*\S)\s*$", line)
        if m and not line.startswith("###"):
            if cur is not None:
                out[cur] = "\n".join(buf)
            cur = m.group(1).strip().lower()
            buf = []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


def table_rows(body: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or set("".join(cells)) <= set("-: "):  # separator row
            continue
        if cells and cells[0].lower() in ("#", "no", "no."):  # header row
            continue
        rows.append(cells)
    return rows


def check_ledger(body: str, root: Path) -> list[str]:
    errs: list[str] = []
    rows = table_rows(body)
    if not rows:
        return ["Claim ledger has no rows"]
    for i, cells in enumerate(rows, 1):
        citation = cells[-1]
        symbol = cells[-2].strip("`").strip() if len(cells) >= 2 else ""
        if not citation or "UNVERIFIED" in citation.upper():
            errs.append(f"ledger row {i}: UNVERIFIED or missing citation")
            continue
        m = CITATION_RE.search(citation)
        if not m:
            errs.append(f"ledger row {i}: citation '{citation}' is not path:line")
            continue
        rel, line = m.group(1), int(m.group(2))
        target = root / rel
        if not target.exists():
            errs.append(f"ledger row {i}: path '{rel}' does not exist")
            continue
        if not target.is_file():  # directory/symlink-to-dir → fail, never crash on read_text
            errs.append(f"ledger row {i}: path '{rel}' is not a file")
            continue
        lines = target.read_text(errors="replace").splitlines()
        if line < 1 or line > len(lines):
            errs.append(f"ledger row {i}: line {line} out of range for {rel} ({len(lines)} lines)")
            continue
        if symbol and symbol not in (chr(10)).join(lines[max(0, line - 1 - PROXIMITY) : line - 1 + PROXIMITY + 1]):
            errs.append(f"ledger row {i}: symbol '{symbol}' not found within ±{PROXIMITY} lines of {rel}:{line}")
    return errs


def check_review(body: str) -> list[str]:
    errs: list[str] = []
    passes = list(PASS_RE.finditer(body))
    if len(passes) < 2:
        errs.append(f"Review log has {len(passes)} Pass entr(ies); need at least two")
        return errs
    if not re.search(r"independent", body, re.IGNORECASE):
        errs.append("Review log has no pass marked 'independent'")
    # final pass = the last Pass header by document order; its body runs to EOF
    final_body = body[passes[-1].end() :]
    if not ZERO_FINDINGS_RE.search(final_body):
        errs.append("final Pass does not state a zero-findings result (e.g. 'no new findings')")
    return errs


def check_plan(path: Path) -> list[str]:
    text = path.read_text(errors="replace")
    secs = sections(text)
    if "claim ledger" not in secs and "review log" not in secs:
        return []  # not a gated plan; skip
    root = repo_root(path)
    errs: list[str] = []
    if "claim ledger" not in secs:
        errs.append("missing '## Claim ledger' section")
    else:
        errs += check_ledger(secs["claim ledger"], root)
    if "review log" not in secs:
        errs.append("missing '## Review log' section")
    else:
        errs += check_review(secs["review log"])
    return errs


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_plan.py <PLAN.md> [more...]", file=sys.stderr)
        return 2
    failed = False
    for arg in argv:
        p = Path(arg)
        errs = check_plan(p)
        if errs:
            failed = True
            print(f"FAIL {arg}")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"ok   {arg}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
