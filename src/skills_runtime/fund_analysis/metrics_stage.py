"""Portfolio metric helper functions for FundAnalysisSkill."""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillInput
from src.tools.fund.metrics import calculate_fund_metrics
from src.tools.portfolio.analysis import (
    calculate_cash_ratio,
    calculate_concentration_metrics,
    calculate_industry_exposure,
    calculate_portfolio_pnl,
    calculate_position_weights,
    calculate_short_term_budget_usage,
    calculate_theme_exposure,
    calculate_trade_budget,
    detect_portfolio_risk_flags,
    review_dca_plan,
    simulate_rebalance,
)
from src.tools.portfolio.transaction import (
    calculate_position_cost_basis,
    detect_trading_discipline_flags,
    normalize_fund_transactions,
    reconcile_portfolio_with_transactions,
    summarize_transaction_ledger,
)

from .context import CoreMetricsBundle, PortfolioInputBundle
from .evidence_stage import evidence_specs
from .input_stage import target_weights_from_payload


def compute_core_metrics(
    bundle: PortfolioInputBundle,
    warnings: list[str],
    skill_input: SkillInput,
) -> CoreMetricsBundle:
    position_weights = calculate_position_weights(bundle.portfolio)
    concentration = calculate_concentration_metrics(bundle.positions)
    exposures = calculate_theme_exposure(
        bundle.positions,
        fund_profiles=bundle.fund_profiles,
        holdings=bundle.holdings,
    )
    cash_ratio = calculate_cash_ratio(bundle.portfolio)
    industry_exposure = calculate_industry_exposure(bundle.positions, bundle.holdings)
    fund_type_exposure = {
        key.replace("fund_type:", ""): round(value, 6)
        for key, value in exposures.items()
        if key.startswith("fund_type:")
    }
    fund_metrics = {
        fund_code: calculate_fund_metrics(bundle.nav_history[fund_code])
        for fund_code in bundle.fund_codes
        if fund_code in bundle.nav_history
    }
    metrics_for_flags = {
        "concentration": concentration,
        "fund_metrics": fund_metrics,
    }
    risk_flags = detect_portfolio_risk_flags(
        portfolio=bundle.portfolio,
        risk_profile=bundle.risk_profile,
        exposures=exposures,
        metrics=metrics_for_flags,
        industry_exposure=industry_exposure,
    )
    pnl_summary = None
    trade_budget = calculate_trade_budget(
        bundle.portfolio,
        bundle.risk_profile,
        bundle.constraints,
    )
    short_term_budget = None
    dca_review = None
    if bundle.positions and any(
        isinstance(p, dict) and p.get("total_cost") is not None
        for p in bundle.positions
    ):
        pnl_summary = calculate_portfolio_pnl(bundle.positions)
    if bundle.transactions:
        short_term_budget = calculate_short_term_budget_usage(
            bundle.positions,
            bundle.transactions,
            bundle.risk_profile,
            bundle.as_of_date,
        )
    if bundle.dca_plans:
        dca_review = review_dca_plan(
            bundle.dca_plans,
            bundle.portfolio,
            bundle.transactions,
            bundle.risk_profile,
        )

    normalized_transactions = []
    ledger_summary = None
    cost_basis_summary = None
    reconciliation = None
    trading_flags: list[dict[str, Any]] = []
    if bundle.transactions:
        normalized_transactions, txn_warnings = normalize_fund_transactions(
            bundle.transactions
        )
        if txn_warnings:
            warnings.extend(txn_warnings)

        # Determine as_of_date for transaction-aware tools:
        # use portfolio.as_of_date or fall back to latest transaction date.
        txn_as_of = bundle.as_of_date
        if not txn_as_of and normalized_transactions:
            txn_dates = [t.date for t in normalized_transactions if t.date]
            if txn_dates:
                txn_as_of = max(txn_dates)

        ledger_summary = summarize_transaction_ledger(
            normalized_transactions,
            bundle.nav_data,
            txn_as_of,
        )
        cost_basis_summary = {
            fund_code: cb.to_dict()
            for fund_code, cb in calculate_position_cost_basis(
                normalized_transactions,
                bundle.nav_data,
                txn_as_of,
            ).items()
        }
        reconciliation = reconcile_portfolio_with_transactions(
            bundle.portfolio,
            ledger_summary,
        )
        trading_flags = detect_trading_discipline_flags(
            normalized_transactions,
            bundle.risk_profile,
            bundle.portfolio,
            txn_as_of,
        )
    scenario_flags = scenario_flags_from_market_scenario(bundle.market_scenario)

    portfolio_summary = build_portfolio_summary(
        bundle.portfolio,
        bundle.fund_codes,
        position_weights,
    )
    all_risk_flags = risk_flags + trading_flags + scenario_flags
    risk_flags_refs = [f["type"] for f in all_risk_flags]
    evidence_ids = [
        f"ev:{spec['metric_name']}"
        for spec in evidence_specs(
            skill_input=skill_input,
            fund_codes=bundle.fund_codes,
            portfolio_summary=portfolio_summary,
            concentration=concentration,
            fund_metrics=fund_metrics,
            risk_flags=all_risk_flags,
            rebalance_plan=None,
            cost_basis_summary=cost_basis_summary,
            short_term_budget=short_term_budget,
            dca_review=dca_review,
            market_scenario=bundle.market_scenario,
            pnl_summary=pnl_summary,
        )
    ]
    target_weights = target_weights_from_payload(bundle.payload, bundle.positions)
    rebalance_plan = (
        simulate_rebalance(
            portfolio=bundle.portfolio,
            target_weights=target_weights,
            constraints=bundle.constraints,
            risk_profile=bundle.risk_profile,
            risk_flags_refs=risk_flags_refs,
            evidence_refs=evidence_ids,
        )
        if target_weights
        else None
    )
    enrich_rebalance_plan_with_positions(
        rebalance_plan,
        bundle.positions,
        pnl_summary,
    )

    return CoreMetricsBundle(
        position_weights=position_weights,
        concentration=concentration,
        exposures=exposures,
        cash_ratio=cash_ratio,
        industry_exposure=industry_exposure,
        fund_type_exposure=fund_type_exposure,
        fund_metrics=fund_metrics,
        risk_flags=risk_flags,
        pnl_summary=pnl_summary,
        trade_budget=trade_budget,
        short_term_budget=short_term_budget,
        dca_review=dca_review,
        normalized_transactions=normalized_transactions,
        ledger_summary=ledger_summary,
        cost_basis_summary=cost_basis_summary,
        reconciliation=reconciliation,
        trading_flags=trading_flags,
        scenario_flags=scenario_flags,
        portfolio_summary=portfolio_summary,
        rebalance_plan=rebalance_plan,
    )


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
