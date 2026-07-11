"""B1 (PLAN-025): clone-URL scheme allow-list + ref option-injection guard.

The dispatch payload's ``context_package.repository.url`` reaches ``git clone``;
an ``ext::`` remote-helper URL is arbitrary shell (RCE) and ``file://`` reads the
host FS. Only ``https``/``ssh`` transports with a non-empty authority are accepted
at the door; a leading-dash ``base_ref``/``default_branch`` (an argv option-injection
that a trailing ``--`` on ``git checkout`` does *not* stop) is rejected too. A
test-only env exemption re-permits ``file`` for the gated local-clone fixtures — it
MUST never be set in production, and it can never re-enable ``ext::`` (the ``clone()``
sink guard refuses the remote-helper form outright).
"""

from __future__ import annotations

from typing import Any

import pytest
from iplan_claude.validation.payload_rules import validate_payload

_SCHEME = "REMOTE.PAYLOAD_REPOSITORY_URL_SCHEME"
_REF = "REMOTE.PAYLOAD_REPOSITORY_REF"


def _payload(
    url: str = "https://example.com/r.git", base_ref: str = "main", default_branch: str = "main"
) -> dict[str, Any]:
    return {
        "org_id": "o",
        "project_id": "p",
        "run_id": "R1",
        "step_id": "S1",
        "task_id": "T1",
        "executor_id": "exec:iopsremote2zqf7kx3a",
        "work_order": {"todos": [{"id": "x"}]},
        "context_package": {"repository": {"url": url, "default_branch": default_branch, "base_ref": base_ref}},
    }


def _codes(payload: dict[str, Any]) -> set[str]:
    return {f.rule_id for f in validate_payload(payload)}


def test_https_repo_url_is_accepted() -> None:
    assert _codes(_payload("https://example.com/r.git")) == set()


def test_ssh_repo_url_is_accepted() -> None:
    assert _SCHEME not in _codes(_payload("ssh://git@example.com/r.git"))


@pytest.mark.parametrize(
    "url",
    [
        "ext::sh -c touch /tmp/pwned",
        "file:///etc/passwd",
        "http://example.com/r.git",
        "git://example.com/r.git",
        "git+ssh://git@example.com/r.git",  # dropped from the allow-list (non-native transport)
        "-oProxyCommand=evil",
        "not-a-url",
        "https://",  # empty authority
        "https:///path",  # empty authority (triple slash)
    ],
)
def test_dangerous_or_malformed_repo_url_is_rejected(url: str) -> None:
    assert _SCHEME in _codes(_payload(url))


@pytest.mark.parametrize("field", ["base_ref", "default_branch"])
@pytest.mark.parametrize("ref", ["--upload-pack=touch /tmp/pwned", "-"])
def test_leading_dash_ref_is_rejected(field: str, ref: str) -> None:
    assert _REF in _codes(_payload(**{field: ref}))


def test_both_a_bad_scheme_and_a_bad_ref_co_emit() -> None:
    codes = _codes(_payload("ext::sh -c x", base_ref="-oProxy"))
    assert _SCHEME in codes and _REF in codes


def test_env_exemption_gates_the_file_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    # Rejected by default (no exemption) ...
    assert _SCHEME in _codes(_payload("file:///srv/repo"))
    # ... and re-permitted only when the test-only exemption is set.
    monkeypatch.setenv("IOPS_INSECURE_CLONE_SCHEMES", "file")
    assert _SCHEME not in _codes(_payload("file:///srv/repo"))


def test_string_repository_shape_bypasses_scheme_check() -> None:
    # The file-intake string form is not a clone target; scheme rules apply only to the object shape.
    payload = _payload()
    payload["context_package"]["repository"] = "some/local/path"
    assert _SCHEME not in _codes(payload)
