"""SLO evaluation against collected samples (exporter-independent).

Samples are supplied as a mapping of metric name -> observed value, so SLO logic
is testable without a live backend. ``met`` is a simple baseline comparison
(value >= objective); direction-aware SLOs are future work.
"""

from __future__ import annotations

from typing import Any


def evaluate_slos(manifest: dict[str, Any], samples: dict[str, float]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for slo in manifest.get("slos", []):
        ref = slo.get("signal_ref")
        objective = slo.get("objective")
        value = samples.get(ref) if ref is not None else None
        met: bool | None
        met = None if value is None or objective is None else value >= objective
        results.append(
            {
                "id": slo.get("id"),
                "signal_ref": ref,
                "objective": objective,
                "value": value,
                "met": met,
            }
        )
    return results
