"""Iplanic remote-executor task-payload validation (category REMOTE-001).

The payload must carry the identity + work that the run loop cannot infer; absent
fields produce findings rather than silent defaults (REMOTE_EXECUTOR_CONTRACT.md).
"""

from __future__ import annotations

import os
import re
from typing import Any

from ._base import Finding, finding

_REQUIRED_IDS = ("org_id", "project_id", "run_id", "step_id", "executor_id")

# Iplanic executor_id hash form (Iplanic §2.1 / D-0031): exec:<base32(sha256(...))>.
_EXECUTOR_ID = re.compile(r"^exec:[a-z2-7]{16,}$")

# A dispatched task carries `context_package.repository` as an OBJECT (Iplanic
# task.schema.json) — the receiver's `adapt_dispatched_task` rewrites it to the
# workspace path before intake, so a malformed object must be caught at the door.
_REPOSITORY_FIELDS = ("url", "default_branch", "base_ref")

# B1 (PLAN-025) — the dispatched `repository.url` reaches `git clone`; git's
# `ext::`/`file://` remote helpers are arbitrary shell / host-FS reads, so the
# clone target must carry an explicit, allow-listed transport scheme AND a non-empty
# authority. Only https/ssh are permitted at the door. `IOPS_INSECURE_CLONE_SCHEMES`
# (comma-list) re-permits extra schemes for the gated local-clone test fixtures
# ONLY — it must never be set in production. (`ext::` stays blocked even when the
# exemption is set: the `clone()` sink guard refuses the remote-helper form outright.)
_SAFE_CLONE_SCHEMES = frozenset({"https", "ssh"})
_URL_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*)://(.*)$", re.DOTALL)


def _allowed_clone_schemes() -> frozenset[str]:
    extra = os.environ.get("IOPS_INSECURE_CLONE_SCHEMES", "")
    exempt = {s.strip().lower() for s in extra.split(",") if s.strip()}
    return _SAFE_CLONE_SCHEMES | exempt


def _clone_url_ok(url: str) -> bool:
    """True only for an explicit `<scheme>://` on the allow-list — rejects `ext::`
    (no `//`), `file://`/`http://`/`git://`, scp-like `host:path`, leading-dash, and
    any non-URL string. Network schemes (https/ssh) also require a non-empty authority
    so an authority-less `https://` is caught at the door instead of crashing deep in
    the worker; a test-only exempted `file:///path` is legitimately authority-less."""
    match = _URL_SCHEME.match(url)
    if not match:
        return False
    scheme, rest = match.group(1).lower(), match.group(2)
    if scheme not in _allowed_clone_schemes():
        return False
    # network schemes (https/ssh) require a non-empty authority; an exempted, test-only
    # `file:///path` is legitimately authority-less.
    return scheme not in _SAFE_CLONE_SCHEMES or (bool(rest) and not rest.startswith("/"))


def validate_payload(payload: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    if any(not payload.get(k) for k in _REQUIRED_IDS):
        findings.append(finding("REMOTE.PAYLOAD_IDS_MISSING", "task payload missing a required identity field"))

    executor_id = payload.get("executor_id")
    if executor_id and not (isinstance(executor_id, str) and _EXECUTOR_ID.match(executor_id)):
        findings.append(
            finding("REMOTE.PAYLOAD_EXECUTOR_ID_FORMAT", "executor_id is not the canonical exec: hash form")
        )

    work_order = payload.get("work_order") or {}
    if not (work_order.get("todos") or []):
        findings.append(finding("REMOTE.PAYLOAD_NO_TODOS", "task payload work_order has no todos"))

    context = payload.get("context_package")
    if not context:
        findings.append(finding("REMOTE.PAYLOAD_CONTEXT_MISSING", "task payload missing context_package"))
    elif isinstance(context, dict):
        # Dispatched shape: repository is an object {url, default_branch, base_ref}.
        # A string repository is the file-intake shape and stays valid (backward
        # compatible); only an object missing required fields is rejected.
        repository = context.get("repository")
        if isinstance(repository, dict):
            if not all(isinstance(repository.get(f), str) and repository.get(f) for f in _REPOSITORY_FIELDS):
                findings.append(
                    finding(
                        "REMOTE.PAYLOAD_REPOSITORY_SHAPE",
                        "context_package.repository object missing url/default_branch/base_ref",
                    )
                )
            else:
                # B1: the fields are non-empty strings — enforce clone safety before they reach git.
                if not _clone_url_ok(repository["url"]):
                    findings.append(
                        finding(
                            "REMOTE.PAYLOAD_REPOSITORY_URL_SCHEME",
                            "context_package.repository.url scheme not in the clone allow-list (https/ssh)",
                        )
                    )
                # A leading-dash ref is an argv option-injection that a trailing `--` on
                # `git checkout` does NOT stop (git still parses it as a switch), so reject here.
                if any(repository[f].startswith("-") for f in ("base_ref", "default_branch")):
                    findings.append(
                        finding(
                            "REMOTE.PAYLOAD_REPOSITORY_REF",
                            "context_package.repository base_ref/default_branch must not start with '-'",
                        )
                    )

    return findings
