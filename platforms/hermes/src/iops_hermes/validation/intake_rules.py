"""IPLAN intake manifest validation (category INTAKE-001)."""

from __future__ import annotations

from typing import Any

from ._base import Finding, finding

SUPPORTED_SCHEMAS = {"1.0"}
EXEC_READY_MIN = 90


def validate_intake(document: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    if document.get("metadata", {}).get("schema_version") not in SUPPORTED_SCHEMAS:
        findings.append(finding("INTAKE.SCHEMA_UNSUPPORTED", "unsupported intake schema_version"))

    control = document.get("intake_control", {})
    if not (
        control.get("source_iplan") and control.get("source_iplan_version") and control.get("source_iplan_checksum")
    ):
        findings.append(finding("INTAKE.SOURCE_MISSING", "source IPLAN id/version/checksum missing"))
    if not control.get("approved") or int(control.get("exec_ready_score") or 0) < EXEC_READY_MIN:
        findings.append(
            finding(
                "INTAKE.APPROVAL_INSUFFICIENT",
                "IPLAN not approved or exec_ready_score below minimum",
            )
        )

    scope = document.get("isolation_scope", {})
    if not (scope.get("client_id") and scope.get("project_id") and scope.get("allowed_roots")):
        findings.append(finding("INTAKE.SCOPE_MISSING", "isolation_scope is incomplete"))

    tasks = document.get("task_graph", [])
    if not tasks:
        findings.append(finding("INTAKE.NO_TASKS", "task_graph is empty"))

    ids = {t.get("task_id") for t in tasks}
    fields_missing = False
    dep_unresolved = False
    for task in tasks:
        if not (task.get("task_id") and task.get("title") and task.get("acceptance")):
            fields_missing = True
        for dep in task.get("depends_on", []):
            if dep not in ids:
                dep_unresolved = True
    if fields_missing:
        findings.append(finding("INTAKE.TASK_FIELDS_MISSING", "a task lacks id/title/acceptance"))
    if dep_unresolved:
        findings.append(finding("INTAKE.DEP_UNRESOLVED", "a depends_on references an unknown task"))

    return findings
