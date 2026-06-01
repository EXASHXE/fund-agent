"""Pure portfolio analysis tool tests."""

from __future__ import annotations

from src.tools.portfolio.analysis import (
    calculate_concentration_metrics,
    calculate_position_weights,
    calculate_theme_exposure,
    detect_portfolio_risk_flags,
)


def test_position_weights_sum_correctly():
    weights = calculate_position_weights(_portfolio(total_value=100000.0))

    assert round(sum(weights.values()), 6) == 1.0
    assert weights["fund_a"] == 0.6
    assert weights["fund_b"] == 0.4


def test_concentration_metrics_detect_overweight_shape():
    metrics = calculate_concentration_metrics(_portfolio()["positions"])

    assert metrics["single_fund_max_weight"] == 0.6
    assert metrics["max_fund_code"] == "fund_a"
    assert metrics["hhi"] == 0.52
    assert "tech" in metrics["duplicate_tags"]


def test_risk_flags_trigger_for_limits_and_cash_reserve():
    portfolio = _portfolio(total_value=100000.0, cash_available=5000.0)
    exposures = calculate_theme_exposure(portfolio["positions"])
    metrics = {"concentration": calculate_concentration_metrics(portfolio["positions"])}
    risk_profile = {
        "risk_level": "moderate",
        "max_single_fund_weight": 0.5,
        "max_theme_weight": 0.5,
        "liquidity_reserve_pct": 0.1,
        "short_term_trade_budget_pct": 0.1,
    }

    flags = detect_portfolio_risk_flags(
        portfolio=portfolio,
        risk_profile=risk_profile,
        exposures=exposures,
        metrics=metrics,
    )
    flag_types = {flag["type"] for flag in flags}

    assert "overweight_single_fund" in flag_types
    assert "overweight_theme" in flag_types
    assert "insufficient_cash_reserve" in flag_types
    assert "duplicate_exposure" in flag_types


def _portfolio(
    total_value: float = 100000.0,
    cash_available: float = 10000.0,
) -> dict:
    return {
        "as_of_date": "2026-06-01",
        "total_value": total_value,
        "cash_available": cash_available,
        "positions": [
            {
                "fund_code": "fund_a",
                "fund_name": "A",
                "current_value": 60000.0,
                "total_cost": 58000.0,
                "tags": ["tech", "growth"],
            },
            {
                "fund_code": "fund_b",
                "fund_name": "B",
                "current_value": 40000.0,
                "total_cost": 39000.0,
                "tags": ["tech", "income"],
            },
        ],
    }
