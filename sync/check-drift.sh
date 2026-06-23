#!/usr/bin/env bash
# Drift-check: iplan-runner's vendored IPLAN-standard surface vs iplan-standard@<tag> (PLAN-023, D-0023).
#
# iplan-runner consumes the IPLAN standard (https://github.com/vladm3105/aidoc-flow-iplan-standard) as a
# vendored, pinned copy. This byte-diffs the BYTE-COPYABLE surface against the pinned tag and fails on drift —
# so iplan-runner can never silently fork the standard (the stale-mirror bug this replaced). Scope:
#   * the vendored iplan_canonical package (*.py) in EACH engine (also enforces cross-engine parity)
#   * the canonicalization golden vectors (*.json)
# The .pyi type stubs are runner-local (not in the tag) and the YAML mirror is a hand-derived subset (not
# byte-comparable to a JSON Schema) — both are intentionally OUT of scope here.
set -euo pipefail

REPO="${IPLAN_STANDARD_REPO:-https://github.com/vladm3105/aidoc-flow-iplan-standard.git}"
TAG="${IPLAN_STANDARD_TAG:-iplan/v0.1.0}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if ! git clone --depth 1 --branch "$TAG" "$REPO" "$tmp" >/dev/null 2>&1; then
  echo "could not clone $REPO@$TAG" >&2
  exit 2
fi

drift=0

# the vendored iplan_canonical package (verbatim copy of the tag) — per engine
for engine in claude hermes; do
  for f in "$tmp"/iplan_canonical/*.py; do
    name="$(basename "$f")"
    local_f="$root/platforms/$engine/src/iplan_$engine/security/iplan_canonical/$name"
    if [ ! -f "$local_f" ]; then
      echo "MISSING ($engine): security/iplan_canonical/$name"
      drift=1
    elif ! cmp -s "$f" "$local_f"; then
      echo "DRIFT ($engine): security/iplan_canonical/$name"
      drift=1
    fi
  done
done

# the canonicalization golden vectors (*.json only; SOURCE.md is runner-local provenance)
for f in "$tmp"/tests/contract/canonicalization/vectors/*.json; do
  name="$(basename "$f")"
  local_f="$root/framework/remote/iplanic-vectors/$name"
  if [ ! -f "$local_f" ]; then
    echo "MISSING (vectors): $name"
    drift=1
  elif ! cmp -s "$f" "$local_f"; then
    echo "DRIFT (vectors): $name"
    drift=1
  fi
done

if [ "$drift" -ne 0 ]; then
  echo ""
  echo "Vendored IPLAN-standard surface has DRIFTED from iplan-standard@$TAG."
  echo "Resolve: re-copy from the tag (re-pin), or push the change upstream to iplan-standard first."
  exit 1
fi

echo "Vendored IPLAN-standard surface is in sync with iplan-standard@$TAG."
