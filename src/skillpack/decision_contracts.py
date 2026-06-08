"""Decision contract loading helpers.

These helpers are intentionally metadata-only. They read the skillpack
decision contract YAML but do not import runtime skill classes, instantiate
skills, call providers, or perform network I/O.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_DECISION_CONTRACTS_PATH = "skillpack/decision-contracts.yaml"


def load_decision_contracts(
    path: str | Path = DEFAULT_DECISION_CONTRACTS_PATH,
) -> dict[str, Any]:
    """Load the decision contract catalog as plain JSON-serializable data."""
    contract_path = _resolve_path(path)
    raw = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"decision contracts must be a mapping: {contract_path}")
    return deepcopy(raw)


def get_decision_contract(
    skill_id: str,
    path: str | Path = DEFAULT_DECISION_CONTRACTS_PATH,
) -> dict[str, Any]:
    """Return one skill's decision contract.

    ``skill_id`` may be a runtime id such as ``decision_support`` or the
    hyphenated Markdown doc slug such as ``decision-support``.
    """
    contracts_doc = load_decision_contracts(path)
    contracts = contracts_doc.get("contracts") or {}
    if not isinstance(contracts, dict):
        raise ValueError("decision contracts file must contain a contracts mapping")

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


def decision_artifact_keys(
    skill_id: str,
    path: str | Path = DEFAULT_DECISION_CONTRACTS_PATH,
) -> list[str]:
    """Return artifact keys from a decision contract in contract order."""
    contract = get_decision_contract(skill_id, path)
    artifact_keys = contract.get("artifact_keys") or []
    keys: list[str] = []
    for artifact in artifact_keys:
        if isinstance(artifact, dict) and artifact.get("key") is not None:
            keys.append(str(artifact["key"]))
    return keys


def active_actions_for_skill(
    skill_id: str,
    path: str | Path = DEFAULT_DECISION_CONTRACTS_PATH,
) -> list[str]:
    """Return active actions from a decision contract."""
    contract = get_decision_contract(skill_id, path)
    return [str(item) for item in contract.get("active_actions") or []]


def passive_actions_for_skill(
    skill_id: str,
    path: str | Path = DEFAULT_DECISION_CONTRACTS_PATH,
) -> list[str]:
    """Return passive actions from a decision contract."""
    contract = get_decision_contract(skill_id, path)
    return [str(item) for item in contract.get("passive_actions") or []]


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate
    if not candidate.is_absolute():
        repo_root = Path(__file__).resolve().parents[2]
        repo_candidate = repo_root / candidate
        if repo_candidate.exists():
            return repo_candidate
    return candidate


def _skill_id_candidates(skill_id: str) -> set[str]:
    raw = str(skill_id or "")
    return {
        raw,
        raw.replace("-", "_"),
        raw.replace("_", "-"),
    }
