"""Report safety boundary helpers.

Handles forbidden execution field detection and safety boundary construction.
"""

from __future__ import annotations

from typing import Any


FORBIDDEN_EXECUTION_FIELDS = frozenset({
    "broker_order_id",
    "order_id",
    "order_status",
    "filled_quantity",
    "fill_price",
    "execution_venue",
    "submitted_at",
    "broker",
    "exchange_order_id",
})


def find_forbidden_execution_fields(data: Any, path: str = "") -> list[str]:
    """Recursively detect forbidden broker/order execution fields.

    Returns list of dotted paths where forbidden fields were found.
    """
    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in FORBIDDEN_EXECUTION_FIELDS:
                found.append(f"{path}.{key}" if path else key)
            if isinstance(value, (dict, list)):
                new_path = f"{path}.{key}" if path else key
                found.extend(find_forbidden_execution_fields(value, new_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, (dict, list)):
                found.extend(find_forbidden_execution_fields(item, f"{path}[{i}]"))
    return found


def build_safety_boundary(
    *,
    ds_has_decision: bool,
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any] | None = None,
    full_report_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the safety boundary section for the final report."""
    analysis_only_sections: list[str] = []

    if fa_artifacts.get("suggested_rebalance_plan"):
        analysis_only_sections.append("suggested_rebalance_plan")
    if fa_artifacts.get("analysis_plan"):
        analysis_only_sections.append("analysis_plan")

    forbidden_found = []
    if full_report_data:
        forbidden_found = find_forbidden_execution_fields(full_report_data)

    formal_source = "none"
    if ds_has_decision:
        formal_source = "decision_support"

    return {
        "no_broker_execution": len(forbidden_found) == 0,
        "forbidden_execution_fields_found": forbidden_found,
        "formal_decision_source": formal_source,
        "analysis_only_sections": analysis_only_sections,
    }
