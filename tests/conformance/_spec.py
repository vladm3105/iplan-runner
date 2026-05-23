"""Shared helpers for the conformance suite."""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK = REPO_ROOT / "framework"


def registry() -> dict[str, Any]:
    return yaml.safe_load((FRAMEWORK / "registry" / "EXECUTION_REGISTRY.yaml").read_text())


def rule_catalog() -> dict[str, Any]:
    return yaml.safe_load((FRAMEWORK / "conformance" / "rule-ids.yaml").read_text())


def framework_version() -> str:
    return (FRAMEWORK / "VERSION").read_text().strip()


def load_yaml(rel_path: str) -> Any:
    return yaml.safe_load((REPO_ROOT / rel_path).read_text())


def vector_pairs() -> list[tuple[Path, Path]]:
    root = FRAMEWORK / "conformance" / "vectors"
    pairs: list[tuple[Path, Path]] = []
    for expect in sorted(root.glob("**/*.expect.yaml")):
        document = expect.with_name(expect.name.replace(".expect.yaml", ".yaml"))
        pairs.append((document, expect))
    return pairs


def load_engines() -> dict[str, Any]:
    """Instantiate adapters for every importable engine (others are skipped)."""
    engines: dict[str, Any] = {}
    for entry in registry().get("engines", []):
        try:
            module = importlib.import_module(entry["package"])
        except Exception:
            continue
        class_name = entry["id"].capitalize() + "Engine"
        adapter = getattr(module, class_name, None)
        if adapter is not None:
            engines[entry["id"]] = adapter()
    return engines
