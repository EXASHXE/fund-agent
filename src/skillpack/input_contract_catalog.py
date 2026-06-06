"""Input contract catalog loading helpers.

These helpers are intentionally metadata-only. They read the skillpack input
contract YAML but do not import runtime skill classes, instantiate skills,
call providers, or perform network I/O.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_INPUT_CONTRACTS_PATH = "skillpack/input-contracts.yaml"


def load_input_contracts(
    path: str | Path = DEFAULT_INPUT_CONTRACTS_PATH,
) -> dict[str, Any]:
    """Load the input contract catalog as plain JSON-serializable data."""
    contract_path = _resolve_path(path)
    raw = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"input contracts must be a mapping: {contract_path}")
    return deepcopy(raw)


def get_skill_input_contract(
    skill_id: str,
    path: str | Path = DEFAULT_INPUT_CONTRACTS_PATH,
) -> dict[str, Any]:
    """Return one skill's input contract by runtime id or Markdown doc slug."""
    contracts_doc = load_input_contracts(path)
    contracts = contracts_doc.get("contracts") or {}
    if not isinstance(contracts, dict):
        raise ValueError("input contracts file must contain a contracts mapping")

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


def recommended_fields_for_skill(
    skill_id: str,
    path: str | Path = DEFAULT_INPUT_CONTRACTS_PATH,
) -> list[str]:
    """Return recommended payload field keys for a skill in contract order."""
    contract = get_skill_input_contract(skill_id, path)
    return _field_keys(contract.get("recommended_fields") or [])


def optional_fields_for_skill(
    skill_id: str,
    path: str | Path = DEFAULT_INPUT_CONTRACTS_PATH,
) -> list[str]:
    """Return optional payload field keys for a skill in contract order."""
    contract = get_skill_input_contract(skill_id, path)
    return _field_keys(contract.get("optional_fields") or [])


def capability_field_mapping_for_skill(
    skill_id: str,
    path: str | Path = DEFAULT_INPUT_CONTRACTS_PATH,
) -> dict[str, list[str]]:
    """Return host capability -> payload field mapping for a skill."""
    contract = get_skill_input_contract(skill_id, path)
    mapping = contract.get("host_data_capability_fields") or {}
    if not isinstance(mapping, dict):
        return {}
    result: dict[str, list[str]] = {}
    for name, info in mapping.items():
        if isinstance(info, dict):
            fields = info.get("payload_fields") or []
        else:
            fields = info
        if isinstance(fields, list):
            result[str(name)] = [str(field) for field in fields]
        else:
            result[str(name)] = []
    return result


def _field_keys(fields: list[Any]) -> list[str]:
    keys: list[str] = []
    for field in fields:
        if isinstance(field, dict) and field.get("key") is not None:
            keys.append(str(field["key"]))
        elif isinstance(field, str):
            keys.append(field)
    return keys


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
