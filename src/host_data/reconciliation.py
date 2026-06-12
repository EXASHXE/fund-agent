"""Provider result reconciliation — detect discrepancies between providers.

Deterministic, no network calls. Does not average or fabricate data.
"""

from __future__ import annotations

from typing import Any

from .provider_result import ProviderResult


def compare_provider_results(results: list[ProviderResult]) -> dict[str, Any]:
    valid = [r for r in results if r.ok]
    if not valid:
        return {
            "status": "INSUFFICIENT",
            "primary_provider": None,
            "accepted_result": None,
            "discrepancies": [],
            "warnings": ["NO_VALID_RESULTS"],
        }

    if len(valid) == 1:
        return {
            "status": "CONSISTENT",
            "primary_provider": valid[0].provider,
            "accepted_result": valid[0],
            "discrepancies": [],
            "warnings": ["SINGLE_SOURCE"],
        }

    discrepancies = _detect_discrepancies(valid)
    primary = valid[0]

    if discrepancies:
        return {
            "status": "DIVERGENT",
            "primary_provider": primary.provider,
            "accepted_result": primary,
            "discrepancies": discrepancies,
            "warnings": [f"DIVERGENT_{len(discrepancies)}_fields"],
        }

    return {
        "status": "CONSISTENT",
        "primary_provider": primary.provider,
        "accepted_result": primary,
        "discrepancies": [],
        "warnings": [],
    }


def _detect_discrepancies(results: list[ProviderResult]) -> list[dict[str, Any]]:
    if len(results) < 2:
        return []

    discrepancies: list[dict[str, Any]] = []
    first = results[0]
    first_data = first.data if isinstance(first.data, dict) else {}

    for other in results[1:]:
        other_data = other.data if isinstance(other.data, dict) else {}
        for key, value in first_data.items():
            if key not in other_data:
                discrepancies.append({
                    "field": key,
                    "providers": [first.provider, other.provider],
                    "issue": "MISSING_IN_SECOND",
                })
                continue
            other_value = other_data[key]
            if isinstance(value, (int, float)) and isinstance(other_value, (int, float)):
                if value != 0 and abs(other_value - value) / abs(value) > 0.01:
                    discrepancies.append({
                        "field": key,
                        "providers": [first.provider, other.provider],
                        "issue": "VALUE_DIVERGENT",
                        "values": {first.provider: value, other.provider: other_value},
                    })
            elif value != other_value:
                discrepancies.append({
                    "field": key,
                    "providers": [first.provider, other.provider],
                    "issue": "VALUE_DIFFERENT",
                    "values": {first.provider: str(value), other.provider: str(other_value)},
                })

    return discrepancies
