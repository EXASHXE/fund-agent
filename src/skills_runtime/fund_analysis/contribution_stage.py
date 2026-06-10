"""Position-level contribution analysis for FundAnalysisSkill.

Deterministic, local-only computation of each position's PnL contribution
to the overall portfolio. Does NOT fetch data, call providers, use LLMs,
or make formal decisions.
"""

from __future__ import annotations

from typing import Any

from .context import CoreMetricsBundle, PortfolioInputBundle


def compute_position_contribution(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any]:
    total_value = float(bundle.portfolio.get("total_value", 0) or 0)
    positions_data: list[dict[str, Any]] = []
    total_abs_pnl = 0.0
    has_any_cost = False

    for pos in bundle.positions:
        if not isinstance(pos, dict) or not pos.get("fund_code"):
            continue
        invested_amount_raw = pos.get("total_cost") or pos.get("invested_amount")
        if invested_amount_raw is not None:
            try:
                _ = float(invested_amount_raw)
                has_any_cost = True
            except (TypeError, ValueError):
                pass

    for pos in bundle.positions:
        if not isinstance(pos, dict) or not pos.get("fund_code"):
            continue
        fund_code = str(pos["fund_code"])
        current_value = float(pos.get("current_value", 0) or 0)
        invested_amount_raw = pos.get("total_cost") or pos.get("invested_amount")
        invested_amount: float | None = None
        if invested_amount_raw is not None:
            try:
                invested_amount = float(invested_amount_raw)
            except (TypeError, ValueError):
                invested_amount = None

        portfolio_weight = round(current_value / total_value, 6) if total_value > 0 else 0.0
        absolute_pnl: float | None = None
        pnl_pct: float | None = None
        if invested_amount is not None:
            absolute_pnl = round(current_value - invested_amount, 2)
            if invested_amount > 0:
                pnl_pct = round(absolute_pnl / invested_amount, 6)

        if absolute_pnl is not None:
            total_abs_pnl += abs(absolute_pnl)

        risk_contribution_hint = _classify_risk_contribution(
            portfolio_weight, absolute_pnl, invested_amount is not None,
        )

        positions_data.append({
            "position_id": fund_code,
            "fund_code": fund_code,
            "fund_name": str(pos.get("fund_name", pos.get("name", ""))),
            "current_value": current_value,
            "invested_amount": invested_amount,
            "absolute_pnl": absolute_pnl,
            "pnl_pct": pnl_pct,
            "portfolio_weight": portfolio_weight,
            "pnl_contribution_pct": None,
            "pnl_contribution_basis": "absolute_pnl",
            "risk_contribution_hint": risk_contribution_hint,
        })

    if total_abs_pnl > 0:
        for entry in positions_data:
            if entry["absolute_pnl"] is not None:
                entry["pnl_contribution_pct"] = round(
                    entry["absolute_pnl"] / total_abs_pnl, 6,
                )

    summary = _build_summary(positions_data, has_any_cost)
    return {
        "positions": positions_data,
        "summary": summary,
    }


def _classify_risk_contribution(
    weight: float,
    pnl: float | None,
    has_cost: bool,
) -> str:
    if not has_cost:
        return "low_data"
    if weight >= 0.30:
        return "high_weight"
    if pnl is not None and pnl > 0:
        return "high_profit_contributor" if weight >= 0.20 else "normal"
    if pnl is not None and pnl < 0:
        return "high_loss_contributor" if abs(pnl) > 5000 else "normal"
    return "normal"


def _build_summary(
    positions: list[dict[str, Any]],
    has_any_cost: bool,
) -> dict[str, Any]:
    largest_value_pos = ""
    largest_profit_pos = ""
    largest_loss_pos = ""
    high_weight_low_contrib: list[str] = []
    small_weight_high_vol: list[str] = []

    max_val = 0.0
    max_profit = 0.0
    max_loss = 0.0

    for p in positions:
        cv = p["current_value"]
        if cv > max_val:
            max_val = cv
            largest_value_pos = p["fund_code"]
        ap = p.get("absolute_pnl")
        if ap is not None:
            if ap > max_profit:
                max_profit = ap
                largest_profit_pos = p["fund_code"]
            if ap < -max_loss:
                max_loss = abs(ap)
                largest_loss_pos = p["fund_code"]
        if p["portfolio_weight"] >= 0.25 and p.get("pnl_contribution_pct", 0) is not None and (p.get("pnl_contribution_pct") or 0) < 0.05:
            high_weight_low_contrib.append(p["fund_code"])

    return {
        "largest_value_position": largest_value_pos,
        "largest_profit_contributor": largest_profit_pos if has_any_cost else "",
        "largest_loss_contributor": largest_loss_pos if has_any_cost else "",
        "high_weight_low_contribution_positions": high_weight_low_contrib,
        "small_weight_high_volatility_hint_positions": small_weight_high_vol,
    }
