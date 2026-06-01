"""Portfolio public API tests — all new v0.4.1 functions."""

from __future__ import annotations

from src.tools.portfolio.analysis import (
    apply_trade_constraints,
    calculate_cash_ratio,
    calculate_industry_exposure,
    calculate_portfolio_pnl,
    calculate_position_pnl,
    calculate_position_weights,
    calculate_short_term_budget_usage,
    calculate_trade_budget,
    rank_trade_plan,
    review_dca_plan,
    summarize_exposure,
)


def test_calculate_position_weights():
    portfolio = {
        "total_value": 120000.0,
        "cash_available": 20000.0,
        "positions": [
            {"fund_code": "A", "current_value": 60000.0},
            {"fund_code": "B", "current_value": 40000.0},
            {"fund_code": "C", "current_value": 20000.0},
        ],
    }

    weights = calculate_position_weights(portfolio)

    assert round(sum(weights.values()), 6) == 1.0
    assert weights["A"] == 0.5
    assert weights["B"] == pytest.approx(1 / 3, rel=1e-5)
    assert weights["C"] == pytest.approx(1 / 6, rel=1e-5)


def test_calculate_cash_ratio():
    portfolio = {
        "total_value": 100000.0,
        "cash_available": 15000.0,
        "positions": [{"fund_code": "A", "current_value": 85000.0}],
    }

    result = calculate_cash_ratio(portfolio)

    assert result == 0.15


def test_calculate_position_pnl():
    positions = [
        {"fund_code": "A", "current_value": 60000.0, "total_cost": 50000.0},
        {"fund_code": "B", "current_value": 40000.0, "total_cost": 45000.0},
        {"fund_code": "C", "current_value": 30000.0, "total_cost": 30000.0},
    ]

    pnl = calculate_position_pnl(positions)

    assert pnl["A"]["unrealized_pnl"] == 10000.0
    assert pnl["A"]["unrealized_pnl_pct"] == 0.2
    assert pnl["B"]["unrealized_pnl"] == -5000.0
    assert pnl["C"]["unrealized_pnl"] == 0.0


def test_calculate_portfolio_pnl():
    positions = [
        {"fund_code": "A", "current_value": 60000.0, "total_cost": 50000.0},
        {"fund_code": "B", "current_value": 40000.0, "total_cost": 45000.0},
    ]

    result = calculate_portfolio_pnl(positions)

    assert result["total_cost"] == 95000.0
    assert result["total_value"] == 100000.0
    assert result["unrealized_pnl"] == 5000.0
    assert "positions" in result
    assert len(result["positions"]) == 2


def test_calculate_trade_budget():
    portfolio = {
        "total_value": 200000.0,
        "cash_available": 30000.0,
        "positions": [{"fund_code": "A", "current_value": 170000.0, "total_cost": 160000.0}],
    }
    risk_profile = {
        "risk_level": "moderate",
        "max_trade_pct": 0.1,
        "short_term_trade_budget_pct": 0.05,
        "liquidity_reserve_pct": 0.1,
    }

    budget = calculate_trade_budget(portfolio, risk_profile)

    assert budget["total_value"] == 200000.0
    assert budget["max_trade_amount"] == 20000.0
    assert budget["short_term_budget"] == 10000.0
    assert budget["liquidity_reserve"] == 20000.0
    assert budget["cash_available"] == 30000.0


def test_calculate_short_term_budget_usage():
    positions = [
        {"fund_code": "A", "current_value": 80000.0, "total_cost": 75000.0},
        {"fund_code": "B", "current_value": 20000.0, "total_cost": 20000.0},
    ]
    transactions = [
        {"action": "BUY", "amount": 2000.0, "date": "2026-06-01"},
        {"action": "SELL", "amount": 1000.0, "date": "2026-05-28"},
    ]
    risk_profile = {
        "short_term_trade_budget_pct": 0.05,
    }

    usage = calculate_short_term_budget_usage(positions, transactions, risk_profile, as_of_date="2026-06-01")

    assert usage["short_term_budget"] == 5000.0
    assert usage["used"] == 3000.0
    assert usage["remaining"] == 2000.0
    assert usage["usage_pct"] == 0.6
    assert usage["exceeded"] is False


def test_review_dca_plan():
    dca_plans = {
        "plan_a": {"fund_code": "A", "monthly_amount": 2000.0},
    }
    portfolio = {
        "total_value": 100000.0,
        "cash_available": 10000.0,
        "positions": [
            {"fund_code": "A", "current_value": 25000.0, "total_cost": 24000.0},
        ],
    }
    risk_profile = {
        "max_single_fund_weight": 0.3,
    }

    result = review_dca_plan(dca_plans, portfolio, None, risk_profile)

    assert len(result["plans"]) == 1
    assert result["plans"][0]["fund_code"] == "A"
    assert result["plans"][0]["suggestion"] in ("CONTINUE", "PAUSE", "REDUCE")


def test_apply_trade_constraints():
    trade_plan = [
        {"fund_code": "A", "action": "BUY", "amount": 15000.0},
        {"fund_code": "B", "action": "SELL", "amount": 30000.0},
    ]
    portfolio = {
        "total_value": 100000.0,
        "cash_available": 5000.0,
        "positions": [
            {"fund_code": "A", "current_value": 30000.0, "total_cost": 29000.0},
            {"fund_code": "B", "current_value": 65000.0, "total_cost": 60000.0},
        ],
    }
    constraints = {"min_trade_amount": 100.0, "forbidden_actions": []}
    risk_profile = {
        "risk_level": "moderate",
        "max_trade_pct": 0.1,
        "liquidity_reserve_pct": 0.05,
        "short_term_trade_budget_pct": 0.1,
    }

    result = apply_trade_constraints(trade_plan, portfolio, constraints, risk_profile)

    assert len(result) > 0
    for trade in result:
        assert trade["amount"] <= trade.get("requested_amount", float("inf"))


def test_calculate_industry_exposure():
    positions = [
        {"fund_code": "A", "current_value": 60000.0},
        {"fund_code": "B", "current_value": 40000.0},
    ]
    holdings = {
        "A": [
            {"name": "Stock1", "weight": 0.5, "industry": "tech", "region": "US"},
            {"name": "Stock2", "weight": 0.5, "industry": "finance", "region": "CN"},
        ],
        "B": [
            {"name": "Stock3", "weight": 0.6, "industry": "tech", "region": "KR"},
            {"name": "Stock4", "weight": 0.4, "industry": "healthcare", "region": "CN"},
        ],
    }

    exposure = calculate_industry_exposure(positions, holdings)

    assert "industry:tech" in exposure
    assert "industry:finance" in exposure
    assert "industry:healthcare" in exposure


def test_rank_trade_plan():
    trades = [
        {"fund_code": "A", "action": "BUY", "amount": 10000.0},
        {"fund_code": "B", "action": "SELL", "amount": 5000.0},
        {"fund_code": "C", "action": "REDUCE", "amount": 3000.0},
    ]
    risk_flags = [
        {"type": "overweight_single_fund", "details": {"fund_code": "B"}},
    ]

    ranked = rank_trade_plan(trades, risk_flags)

    assert len(ranked) == 3
    assert ranked[0]["fund_code"] == "B"
    assert ranked[0]["priority"] == "risk_reduction"
    assert all("rank" in t for t in ranked)


def test_summarize_exposure():
    theme = {"tag:tech": 0.6, "tag:finance": 0.4}
    industry = {"industry:tech": 0.5, "industry:finance": 0.3}
    fund_type = {"fund_type:equity:equity": 0.7}

    summary = summarize_exposure(theme, industry, fund_type)

    assert summary["theme_exposure"] == theme
    assert summary["industry_exposure"] == industry
    assert summary["fund_type_exposure"] == fund_type


import pytest
