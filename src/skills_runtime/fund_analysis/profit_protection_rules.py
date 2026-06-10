"""Profit protection diagnostics for FundAnalysisSkill.

Deterministic, local-only analysis of high-profit positions and their
protection status. This is NOT a formal decision. It produces analysis-only
artifacts for the external host/agent to consume.

Does NOT fetch data, call providers, use LLMs, or make formal decisions.
suggested_analysis_action is always analysis-only: watch, hold_bias,
trim_review, or data_needed.
"""

from __future__ import annotations

from typing import Any

from .context import CoreMetricsBundle, PortfolioInputBundle


def compute_profit_protection_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any]:
    total_value = float(bundle.portfolio.get("total_value", 0) or 0)
    items: list[dict[str, Any]] = []
    has_high_profit = False
    has_principal_recovery = False
    highest_profit_fund = ""
    highest_profit_pct = 0.0
    notes: list[str] = []

    for pos in bundle.positions:
        if not isinstance(pos, dict) or not pos.get("fund_code"):
            continue
        fund_code = str(pos["fund_code"])
        fund_name = str(pos.get("fund_name", pos.get("name", "")))
        current_value = float(pos.get("current_value", 0) or 0)
        invested_raw = pos.get("total_cost") or pos.get("invested_amount")
        invested_amount: float | None = None
        if invested_raw is not None:
            try:
                invested_amount = float(invested_raw)
            except (TypeError, ValueError):
                invested_amount = None

        absolute_pnl: float | None = None
        pnl_pct: float | None = None
        if invested_amount is not None:
            absolute_pnl = round(current_value - invested_amount, 2)
            if invested_amount > 0:
                pnl_pct = round(absolute_pnl / invested_amount, 6)

        profit_level = _classify_profit_level(pnl_pct)
        portfolio_weight = round(current_value / total_value, 6) if total_value > 0 else 0.0

        principal_recovered, free_carry = _assess_principal_recovery(
            fund_code, bundle.transactions, invested_amount, current_value,
        )
        trim_pressure = _classify_trim_pressure(profit_level, portfolio_weight)
        hold_pressure = _classify_hold_pressure(profit_level, principal_recovered)
        watch_condition = _build_watch_condition(profit_level, trim_pressure, free_carry)
        action = _suggest_action(profit_level, trim_pressure, principal_recovered, free_carry)

        if profit_level in ("high", "very_high"):
            has_high_profit = True
        if principal_recovered in ("likely", "partial"):
            has_principal_recovery = True
        if pnl_pct is not None and pnl_pct > highest_profit_pct:
            highest_profit_pct = pnl_pct
            highest_profit_fund = fund_code

        items.append({
            "fund_code": fund_code,
            "fund_name": fund_name,
            "current_value": current_value,
            "invested_amount": invested_amount,
            "absolute_pnl": absolute_pnl,
            "pnl_pct": pnl_pct,
            "profit_level": profit_level,
            "principal_recovered": principal_recovered,
            "free_carry_estimate": free_carry,
            "trim_pressure": trim_pressure,
            "hold_pressure": hold_pressure,
            "watch_condition": watch_condition,
            "suggested_analysis_action": action,
        })

    if not items:
        notes.append("no positions available for profit protection analysis")
    if not any(isinstance(bundle.transactions, list) and bundle.transactions for _ in [1]):
        notes.append("transaction history missing; principal_recovered and free_carry may be unknown")

    return {
        "items": items,
        "summary": {
            "has_high_profit_positions": has_high_profit,
            "has_principal_recovery_candidates": has_principal_recovery,
            "highest_profit_fund_code": highest_profit_fund,
            "notes": notes,
        },
    }


def _classify_profit_level(pnl_pct: float | None) -> str:
    if pnl_pct is None:
        return "unknown"
    if pnl_pct < 0:
        return "none"
    if pnl_pct < 0.05:
        return "low"
    if pnl_pct < 0.15:
        return "moderate"
    if pnl_pct < 0.30:
        return "high"
    return "very_high"


def _assess_principal_recovery(
    fund_code: str,
    transactions: Any,
    invested_amount: float | None,
    current_value: float,
) -> tuple[str, str]:
    if not isinstance(transactions, list) or not transactions:
        return "unknown", "unknown"

    total_buy = 0.0
    total_sell = 0.0
    for txn in transactions:
        if not isinstance(txn, dict) or txn.get("fund_code") != fund_code:
            continue
        action = str(txn.get("action", "")).upper()
        amount = 0.0
        try:
            amount = float(txn.get("amount", 0) or 0)
        except (TypeError, ValueError):
            continue
        if action == "BUY":
            total_buy += amount
        elif action in ("SELL", "REDEEM", "REDEMPTION"):
            total_sell += amount

    if total_buy <= 0:
        return "unknown", "unknown"

    if total_sell >= total_buy and current_value > 0:
        return "likely", "likely"
    if total_sell > 0 and total_sell < total_buy and current_value > 0:
        return "partial", "partial"
    if total_sell <= 0:
        return "false", "none"
    return "unknown", "unknown"


def _classify_trim_pressure(
    profit_level: str,
    portfolio_weight: float,
) -> str:
    if profit_level in ("high", "very_high") and portfolio_weight >= 0.25:
        return "high"
    if profit_level in ("high", "very_high") and portfolio_weight >= 0.15:
        return "medium"
    if profit_level in ("moderate",) and portfolio_weight >= 0.25:
        return "medium"
    if profit_level == "unknown":
        return "unknown"
    return "low"


def _classify_hold_pressure(
    profit_level: str,
    principal_recovered: str,
) -> str:
    if profit_level in ("high", "very_high") and principal_recovered == "likely":
        return "low"
    if profit_level in ("high", "very_high"):
        return "medium"
    if profit_level in ("moderate",):
        return "medium"
    if profit_level == "unknown":
        return "unknown"
    return "low"


def _build_watch_condition(
    profit_level: str,
    trim_pressure: str,
    free_carry: str,
) -> str:
    if profit_level in ("high", "very_high") and trim_pressure == "high":
        return "high_profit_high_weight_monitor"
    if profit_level in ("high", "very_high") and free_carry == "likely":
        return "free_carry_candidate"
    if profit_level in ("high", "very_high"):
        return "high_profit_watch"
    if profit_level in ("moderate",):
        return "moderate_profit_watch"
    return "normal"


def _suggest_action(
    profit_level: str,
    trim_pressure: str,
    principal_recovered: str,
    free_carry: str,
) -> str:
    if profit_level == "unknown":
        return "data_needed"
    if trim_pressure == "high":
        return "trim_review"
    if profit_level in ("high", "very_high") and principal_recovered == "likely":
        return "hold_bias"
    if profit_level in ("high", "very_high"):
        return "watch"
    if profit_level in ("moderate",):
        return "watch"
    return "watch"
