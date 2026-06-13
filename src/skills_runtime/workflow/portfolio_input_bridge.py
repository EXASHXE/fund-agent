"""Portfolio input bridge — deterministic converter from portfolio input to fund_analysis payload.

Reads validated portfolio input dict, produces fund_analysis input payload.
Never fetches live data. Never executes trades.
"""

from __future__ import annotations

from typing import Any


def bridge_portfolio_input(portfolio_input: dict[str, Any]) -> dict[str, Any]:
    """Convert a validated fund_portfolio_input dict into a fund_analysis SkillInput payload.

    Preserves user_question, analysis_mode, risk_profile, constraints.
    Attaches provider_data_snapshot as host evidence.
    Emits data_quality warnings.
    Never fetches live data. Never executes trades.
    """
    if not isinstance(portfolio_input, dict):
        return {"payload": {}, "warnings": ["INVALID_INPUT: portfolio_input must be a dict"]}

    warnings: list[str] = []
    holdings = portfolio_input.get("holdings", [])
    if not holdings:
        warnings.append("EMPTY_HOLDINGS: no holdings provided")

    positions = []
    for h in holdings:
        if not isinstance(h, dict):
            continue
        pos: dict[str, Any] = {
            "fund_code": h.get("fund_code", ""),
            "fund_name": h.get("fund_name", ""),
            "current_value": h.get("current_value", 0),
        }
        cost_basis_val = h.get("cost_basis")
        if cost_basis_val is not None:
            pos["total_cost"] = cost_basis_val
        else:
            pos["cost_basis_missing"] = True
            pos["cost_basis_confidence"] = "unknown"
        if h.get("units") is not None:
            pos["shares"] = h["units"]
        if h.get("unrealized_pnl") is not None:
            pos["unrealized_pnl"] = h["unrealized_pnl"]
        if h.get("unrealized_pnl_pct") is not None:
            pos["unrealized_pnl_pct"] = h["unrealized_pnl_pct"]
        if h.get("holding_days") is not None:
            pos["holding_days"] = h["holding_days"]
        positions.append(pos)

    total_value = sum(p.get("current_value", 0) for p in positions)
    cash_available = 0.0
    cash_alloc = portfolio_input.get("cash_allocation")
    if isinstance(cash_alloc, dict):
        cash_available = cash_alloc.get("cash_available", 0) or 0

    cost_basis_missing = []
    for h in holdings:
        if isinstance(h, dict) and h.get("cost_basis") is None:
            cost_basis_missing.append(h.get("fund_code", "unknown"))
    if cost_basis_missing:
        warnings.append(f"MISSING_COST_BASIS: {', '.join(cost_basis_missing)}")

    snapshot_ref = portfolio_input.get("provider_data_snapshot_ref")
    if not snapshot_ref:
        warnings.append("NO_PROVIDER_SNAPSHOT: no provider_data_snapshot_ref provided; analysis will be limited")

    analysis_mode = portfolio_input.get("analysis_mode", "report_only")
    if analysis_mode == "formal_trade_decision":
        warnings.append("FORMAL_DECISION_REQUESTED: decision_support will be needed for formal trade decisions")

    user_question = portfolio_input.get("user_question", "")

    payload: dict[str, Any] = {
        "portfolio": {
            "as_of_date": portfolio_input.get("as_of_date", ""),
            "total_value": total_value,
            "cash_available": cash_available,
            "positions": positions,
        },
        "user_question": user_question,
        "analysis_mode": analysis_mode,
    }

    if portfolio_input.get("risk_profile_ref"):
        payload["risk_profile_ref"] = portfolio_input["risk_profile_ref"]
    if portfolio_input.get("constraints_ref"):
        payload["constraints_ref"] = portfolio_input["constraints_ref"]
    if snapshot_ref:
        payload["provider_data_snapshot_ref"] = snapshot_ref

    data_quality = portfolio_input.get("data_quality", {})
    if isinstance(data_quality, dict):
        missing = data_quality.get("missing_fields", [])
        if missing:
            warnings.append(f"DATA_QUALITY_MISSING: {', '.join(missing)}")

    privacy_mode = portfolio_input.get("privacy_mode", "full")
    if privacy_mode != "full":
        payload["privacy_mode"] = privacy_mode

    user_prefs = portfolio_input.get("user_preferences", {})
    if isinstance(user_prefs, dict):
        payload["language"] = user_prefs.get("language", "zh-CN")
        payload["report_style"] = user_prefs.get("report_style", "detailed")

    return {
        "payload": payload,
        "warnings": warnings,
    }
