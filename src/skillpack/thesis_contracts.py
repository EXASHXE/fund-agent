"""Thesis contract loader helpers.

Reads skillpack/thesis-contracts.yaml and provides accessors for contract
metadata, artifact keys, and thesis draft field definitions.

Rules:
- No runtime skill imports.
- No provider SDK imports.
- No network calls.
- Returns JSON-serializable plain dict/list objects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        root = Path(__file__).resolve().parents[2]
        p = root / p
    return p


def load_thesis_contracts(path: str | Path = "skillpack/thesis-contracts.yaml") -> dict[str, Any]:
    """Load the full thesis contracts document."""
    with open(_resolve_path(path), encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_thesis_contract(
    skill_id: str,
    path: str | Path = "skillpack/thesis-contracts.yaml",
) -> dict[str, Any]:
    """Get the contract entry for a given skill id.

    Supports both ``thesis_generation`` and ``thesis-generation``.
    """
    doc = load_thesis_contracts(path)
    contracts = doc.get("contracts", {})
    lookup = skill_id.replace("-", "_")
    for key, value in contracts.items():
        if key.replace("-", "_") == lookup:
            return value
    raise KeyError(f"Thesis contract not found for skill_id: {skill_id}")


def thesis_artifact_keys(
    skill_id: str,
    path: str | Path = "skillpack/thesis-contracts.yaml",
) -> list[str]:
    """Return the required artifact keys for a thesis skill."""
    contract = get_thesis_contract(skill_id, path)
    return [a["key"] for a in contract.get("artifact_keys", []) if a.get("required")]
