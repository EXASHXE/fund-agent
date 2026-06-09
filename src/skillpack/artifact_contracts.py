"""Artifact contract loading helpers.

These helpers are intentionally metadata-only. They read the skillpack
artifact contract YAML but do not import runtime skill classes, instantiate
skills, call providers, or perform network I/O.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from src.skillpack.resources import resolve_resource_path

DEFAULT_ARTIFACT_CONTRACTS_PATH = "skillpack/artifact-contracts.yaml"


def load_artifact_contracts(
    path: str | Path = DEFAULT_ARTIFACT_CONTRACTS_PATH,
) -> dict[str, Any]:
    """Load the artifact contract catalog as plain JSON-serializable data."""
    contract_path = _resolve_path(path)
    raw = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"artifact contracts must be a mapping: {contract_path}")
    return deepcopy(raw)


def get_skill_artifact_contract(
    skill_id: str,
    path: str | Path = DEFAULT_ARTIFACT_CONTRACTS_PATH,
) -> dict[str, Any]:
    """Return one skill's artifact contract.

    ``skill_id`` may be a runtime id such as ``fund_analysis`` or the
    hyphenated Markdown doc slug such as ``fund-analysis``.
    """
    contracts_doc = load_artifact_contracts(path)
    contracts = contracts_doc.get("contracts") or {}
    if not isinstance(contracts, dict):
        raise ValueError("artifact contracts file must contain a contracts mapping")

    candidates = _skill_id_candidates(skill_id)
    for contract_key, contract in contracts.items():
        if not isinstance(contract, dict):
            continue
        names = {
            str(contract_key),
            str(contract.get("runtime_id") or ""),
            str(contract.get("doc_slug") or ""),
        }
        if candidates & names:
            return deepcopy(contract)
    raise KeyError(skill_id)


def artifact_keys_for_skill(
    skill_id: str,
    path: str | Path = DEFAULT_ARTIFACT_CONTRACTS_PATH,
) -> list[str]:
    """Return artifact keys from a skill artifact contract in contract order."""
    contract = get_skill_artifact_contract(skill_id, path)
    artifacts = contract.get("artifacts") or []
    keys: list[str] = []
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("key") is not None:
            keys.append(str(artifact["key"]))
    return keys


def forbidden_artifacts_for_skill(
    skill_id: str,
    path: str | Path = DEFAULT_ARTIFACT_CONTRACTS_PATH,
) -> list[str]:
    """Return forbidden artifact keys for a skill artifact contract."""
    contract = get_skill_artifact_contract(skill_id, path)
    return [str(item) for item in contract.get("forbidden_artifacts") or []]


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    resolved = resolve_resource_path(candidate)
    if resolved.exists():
        return resolved
    return resolved


def _skill_id_candidates(skill_id: str) -> set[str]:
    raw = str(skill_id or "")
    return {
        raw,
        raw.replace("-", "_"),
        raw.replace("_", "-"),
    }
