#!/usr/bin/env bash
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"   # the master skill dir
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
git init -q "$tmp/repoA"
printf '.agents/\n' > "$tmp/repoA/.gitignore"   # a repo that ignores .agents/
base="$tmp/repoA/.agents/skills/verified-planning"

# seed the repo as an OLDER installer left it, so the run below exercises the
# self-heal path and not just a clean install
mkdir -p "$base"
printf 'stale skill, no circuit-breaker\n' > "$base/SKILL.md"
printf 'stale installer\n' > "$base/install.sh"

bash "$SRC/install.sh" "$tmp/repoA"

# the gate belongs in the repo — CI and the hook run from the checkout
for f in check_plan.py PLAN.md DESIGN.md PLAN-TEMPLATE.snippet.md README.md; do
  test -f "$base/$f" || { echo "FAIL: missing $f"; exit 1; }
done
test -f "$base/tests/test_check_plan.py" || { echo "FAIL: tests not copied"; exit 1; }
test -f "$tmp/repoA/.github/workflows/plan-gate.yml" || { echo "FAIL: ci"; exit 1; }
grep -q 'verified-planning skill must be committed' "$tmp/repoA/.gitignore" \
  || { echo "FAIL: gitignore not un-ignored"; exit 1; }
git -C "$tmp/repoA" check-ignore -q .agents/skills/verified-planning/check_plan.py \
  && { echo "FAIL: gate still ignored after install"; exit 1; }

# the skill does NOT — the user skill masks a same-name project SKILL.md, leaving
# a duplicate that can drift while appearing authoritative. install.sh must not
# travel either: a repo carrying its own copy can re-infect itself with a stale
# copy list. Both assertions are the point of this file.
test ! -e "$base/SKILL.md" \
  || { echo "FAIL: SKILL.md installed — it is masked by the user skill"; exit 1; }
test ! -e "$base/install.sh" \
  || { echo "FAIL: install.sh installed — re-infection path"; exit 1; }

# and the README that tells the next person why the directory looks incomplete
# Literal Markdown backticks are intentional.
# shellcheck disable=SC2016
grep -q 'Do not add a `SKILL.md` here' "$base/README.md" \
  || { echo "FAIL: README missing the do-not-add warning"; exit 1; }
grep -qF "$SRC/install.sh" "$base/README.md" \
  || { echo "FAIL: README refresh line does not name the installing master"; exit 1; }
grep 'Refresh this directory' "$base/README.md" | grep -qE '__SRC__|~/\.claude' \
  && { echo "FAIL: README refresh line has placeholder or hardcoded layout"; exit 1; }

# garbage in: refuse non-directories and non-git roots without creating anything
if bash "$SRC/install.sh" "$tmp/does-not-exist" >/dev/null 2>&1; then
  echo "FAIL: accepted a nonexistent dir"; exit 1
fi
mkdir -p "$tmp/notgit"
if bash "$SRC/install.sh" "$tmp/notgit" >/dev/null 2>&1; then
  echo "FAIL: accepted a non-git dir"; exit 1
fi
[ -e "$tmp/notgit/.agents" ] && { echo "FAIL: created dirs in refused repo"; exit 1; }

# consumer tweaks survive a re-run: differing files are skipped, exit 1
echo "# consumer tuning" >> "$tmp/repoA/.github/workflows/plan-gate.yml"
echo "# consumer threshold" >> "$base/check_plan.py"
if bash "$SRC/install.sh" "$tmp/repoA" >/dev/null 2>&1; then
  echo "FAIL: re-run over differing files exited 0"; exit 1
fi
grep -q 'consumer tuning' "$tmp/repoA/.github/workflows/plan-gate.yml" \
  || { echo "FAIL: workflow clobbered"; exit 1; }
grep -q 'consumer threshold' "$base/check_plan.py" \
  || { echo "FAIL: gate file clobbered"; exit 1; }

# --force restores, --backup keeps what it replaced
bash "$SRC/install.sh" --force --backup "$tmp/bak" "$tmp/repoA" >/dev/null 2>&1 \
  || { echo "FAIL: --force run failed"; exit 1; }
cmp -s "$SRC/check_plan.py" "$base/check_plan.py" \
  || { echo "FAIL: --force did not restore gate file"; exit 1; }
grep -q 'consumer threshold' "$tmp/bak/.agents/skills/verified-planning/check_plan.py" \
  || { echo "FAIL: backup missing replaced content"; exit 1; }

# --dry-run changes nothing
git init -q "$tmp/repoB"
bash "$SRC/install.sh" --dry-run "$tmp/repoB" >/dev/null 2>&1 \
  || { echo "FAIL: --dry-run failed"; exit 1; }
[ -e "$tmp/repoB/.agents" ] && { echo "FAIL: --dry-run created files"; exit 1; }
[ -e "$tmp/repoB/.github" ] && { echo "FAIL: --dry-run created files"; exit 1; }

# ignore-variant coverage: `.agents/*` hides the gate exactly like `.agents/`
git init -q "$tmp/repoC"
printf '.agents/*\n' > "$tmp/repoC/.gitignore"
bash "$SRC/install.sh" "$tmp/repoC" >/dev/null 2>&1 \
  || { echo "FAIL: install into .agents/* repo failed"; exit 1; }
git -C "$tmp/repoC" check-ignore -q .agents/skills/verified-planning/check_plan.py \
  && { echo "FAIL: gate still ignored under .agents/* variant"; exit 1; }

echo "PASS"
