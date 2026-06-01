"""Structured fund metrics tests — period returns, rolling drawdown, risk-adjusted score."""

from __future__ import annotations

import pytest

from src.tools.fund.metrics import (
    calculate_fund_metrics,
    calculate_period_return,
    calculate_rolling_drawdown,
    normalize_nav_history,
)


def _nav_6m():
    return [
        {"date": "2025-12-01", "nav": 1.00},
        {"date": "2026-01-01", "nav": 1.02},
        {"date": "2026-02-01", "nav": 1.04},
        {"date": "2026-03-01", "nav": 1.03},
        {"date": "2026-04-01", "nav": 1.06},
        {"date": "2026-05-01", "nav": 1.08},
        {"date": "2026-06-01", "nav": 1.10},
    ]


def _nav_1m():
    return [
        {"date": "2026-05-01", "nav": 1.05},
        {"date": "2026-06-01", "nav": 1.08},
    ]


def test_calculate_period_return_1m():
    points = normalize_nav_history(_nav_6m())

    ret = calculate_period_return(points, 1)

    assert ret is not None
    assert ret == round((1.10 - 1.08) / 1.08, 6)


def test_calculate_period_return_6m():
    points = normalize_nav_history(_nav_6m())

    ret = calculate_period_return(points, 6)

    assert ret is not None
    assert ret == pytest.approx(0.10, rel=1e-5)


def test_calculate_rolling_drawdown():
    nav = [
        {"date": "2026-01-01", "nav": 1.00},
        {"date": "2026-01-02", "nav": 1.10},
        {"date": "2026-01-03", "nav": 0.90},
        {"date": "2026-01-04", "nav": 1.05},
    ]
    points = normalize_nav_history(nav)

    result = calculate_rolling_drawdown(points)

    assert result["max_drawdown"] == pytest.approx(0.2 / 1.10, rel=1e-5)
    assert result["peak_nav"] == 1.10
    assert result["trough_nav"] == 0.90


def test_calculate_fund_metrics_returns_all_fields():
    metrics = calculate_fund_metrics(_nav_6m())

    required_fields = {
        "observation_count", "return_count", "total_return",
        "annualized_volatility", "max_drawdown", "sharpe", "sortino",
        "return_1m", "return_3m", "return_6m", "return_1y",
        "recent_momentum", "risk_adjusted_score", "rolling_drawdown",
    }
    for field in required_fields:
        assert field in metrics, f"Missing field: {field}"

    assert isinstance(metrics["rolling_drawdown"], dict)
    assert "max_drawdown" in metrics["rolling_drawdown"]
    assert "peak_nav" in metrics["rolling_drawdown"]
    assert "trough_nav" in metrics["rolling_drawdown"]


def test_insufficient_nav_handled():
    points = normalize_nav_history([{"date": "2026-06-01", "nav": 1.0}])

    ret1m = calculate_period_return(points, 1)
    ret6m = calculate_period_return(points, 6)

    assert ret1m is None
    assert ret6m is None


def test_recent_momentum():
    metrics = calculate_fund_metrics(_nav_6m())

    assert "recent_momentum" in metrics
    assert isinstance(metrics["recent_momentum"], float)


def test_risk_adjusted_score():
    nav = [
        {"date": "2025-12-01", "nav": 1.00},
        {"date": "2026-01-01", "nav": 1.05},
        {"date": "2026-02-01", "nav": 1.08},
        {"date": "2026-03-01", "nav": 1.04},
        {"date": "2026-04-01", "nav": 1.09},
        {"date": "2026-05-01", "nav": 1.12},
        {"date": "2026-06-01", "nav": 1.15},
    ]
    metrics = calculate_fund_metrics(nav)

    assert "risk_adjusted_score" in metrics
    if metrics["annualized_volatility"] > 0:
        assert metrics["risk_adjusted_score"] != 0.0
    else:
        assert metrics["risk_adjusted_score"] == 0.0
