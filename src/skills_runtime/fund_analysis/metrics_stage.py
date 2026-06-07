"""Portfolio metric helper functions for FundAnalysisSkill."""

from __future__ import annotations

from typing import Any


def suggested_watchlist(
    fund_metrics: dict[str, Any],
    risk_flags: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    watchlist: list[dict[str, Any]] = []
    flagged_funds = {
        flag.get("details", {}).get("fund_code")
        for flag in risk_flags
        if flag.get("details", {}).get("fund_code")
    }
    for fund_code, metrics in fund_metrics.items():
        if fund_code in flagged_funds or float(metrics.get("max_drawdown", 0.0)) > 0.2:
            watchlist.append(
                {
                    "fund_code": fund_code,
                    "reason": "drawdown or concentration risk requires monitoring",
                }
            )
    return watchlist


def scenario_flags_from_market_scenario(
    market_scenario: dict[str, Any],
) -> list[dict[str, Any]]:
    scenario_flags: list[dict[str, Any]] = []
    if market_scenario:
        scenario_flags.append({
            "type": "market_scenario",
            "severity": "high" if market_scenario.get("risk_level") == "high" else "medium",
            "message": f"Host-provided market scenario: {market_scenario.get('name', 'unknown')}",
            "details": {"scenario": market_scenario},
        })
    return scenario_flags


def build_portfolio_summary(
    portfolio: dict[str, Any],
    fund_codes: list[str],
    position_weights: dict[str, Any],
) -> dict[str, Any]:
    return {
        "as_of_date": portfolio.get("as_of_date", ""),
        "total_value": float(portfolio.get("total_value", 0.0) or 0.0),
        "cash_available": float(portfolio.get("cash_available", 0.0) or 0.0),
        "position_count": len(fund_codes),
        "position_weights": position_weights,
    }


def build_position_summary(positions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        p["fund_code"]: {
            "fund_code": p.get("fund_code"),
            "fund_name": p.get("fund_name", p.get("name", "")),
            "current_value": p.get("current_value", 0.0),
            "total_cost": p.get("total_cost"),
            "shares": p.get("shares"),
            "target_weight": p.get("target_weight"),
            "tags": p.get("tags", []),
            "pending_amount": p.get("pending_amount", 0.0),
        }
        for p in positions
        if isinstance(p, dict) and p.get("fund_code")
    }


def enrich_rebalance_plan_with_positions(
    rebalance_plan: dict[str, Any] | None,
    positions: list[dict[str, Any]],
    pnl_summary: dict[str, Any] | None,
) -> None:
    if rebalance_plan is None:
        return
    position_map = {p["fund_code"]: p for p in positions if isinstance(p, dict) and p.get("fund_code")}
    pos_pnl_map = pnl_summary.get("positions", {}) if pnl_summary else {}
    for trade_leg in rebalance_plan.get("suggested_trade_plan", []):
        fund_code = trade_leg.get("fund_code", "")
        pos = position_map.get(fund_code, {})
        trade_leg["fund_name"] = pos.get("fund_name", pos.get("name", fund_code))
        trade_leg["current_value"] = pos.get("current_value", 0.0)
        trade_leg["current_cost"] = pos.get("total_cost")
        trade_leg["unrealized_pnl"] = pos_pnl_map.get(fund_code, {}).get("unrealized_pnl")
        trade_leg["cap_reasons"] = trade_leg.get("cap_reasons", [])
        trade_leg["rationale"] = ""
        if trade_leg.get("capped"):
            trade_leg["rationale"] = "Capped by constraints" + (
                f": {', '.join(trade_leg['cap_reasons'])}"
                if trade_leg.get("cap_reasons") else ""
            )
        else:
            trade_leg["rationale"] = "Within constraint bounds"
        trade_leg["tags"] = pos.get("tags", [])
