"""Pure financial mathematics tools — portfolio metrics. No IO, no network, no LLM."""

from __future__ import annotations

import math
import statistics


def calculate_sharpe(daily_returns: list[float], risk_free_annual: float = 0.02) -> float:
    """Calculate annualized Sharpe ratio. Pure math, no IO.

    Args:
        daily_returns: List of daily return fractions (e.g. [0.001, -0.002, ...]).
        risk_free_annual: Annual risk-free rate (default 2 %, i.e. 0.02).

    Returns:
        Annualized Sharpe ratio.  0.0 if fewer than 2 returns or zero std dev.
    """
    if not daily_returns or len(daily_returns) < 2:
        return 0.0

    mean_ret = statistics.mean(daily_returns)
    std_ret = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.0

    if std_ret == 0:
        return 0.0

    risk_free_daily = (1 + risk_free_annual) ** (1 / 252) - 1
    return (mean_ret - risk_free_daily) / std_ret * math.sqrt(252)


def calculate_sortino(daily_returns: list[float], mar_annual: float = 0.025) -> float:
    """Calculate Sortino ratio. Delegates to existing implementation.

    Args:
        daily_returns: List of daily return fractions.
        mar_annual: Minimum acceptable return (annual, default 2.5 %).

    Returns:
        Annualized Sortino ratio.
    """
    from src.tools.risk.metrics import sortino_ratio

    return sortino_ratio(daily_returns, mar_annual)


def calculate_max_drawdown(nav_series: list[float]) -> float:
    """Calculate max drawdown from NAV series. Returns positive percentage (0.0 to 1.0).

    Args:
        nav_series: List of NAV values in chronological order.

    Returns:
        Maximum drawdown as a positive fraction (e.g. 0.2 = 20 %).
        0.0 if empty or single value.
    """
    if not nav_series:
        return 0.0

    peak = nav_series[0]
    max_dd = 0.0

    for nav in nav_series:
        if nav > peak:
            peak = nav
        dd = (peak - nav) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    return max_dd


def calculate_volatility(daily_returns: list[float]) -> float:
    """Calculate annualized volatility.

    Args:
        daily_returns: List of daily return fractions.

    Returns:
        Annualized volatility as a fraction (e.g. 0.15 = 15 %).
        0.0 if fewer than 2 returns.
    """
    if not daily_returns or len(daily_returns) < 2:
        return 0.0

    return statistics.stdev(daily_returns) * math.sqrt(252)


def calculate_hhi(holdings_weights: list[float]) -> float:
    """Calculate Herfindahl-Hirschman Index. Delegates to existing implementation.

    Args:
        holdings_weights: List of holding weights in 0-1 scale.

    Returns:
        HHI value.  0.0 if empty or computation fails.
    """
    from src.tools.math.calc import compute_hhi
    import pandas as pd

    df = pd.DataFrame({"weight": holdings_weights})
    result = compute_hhi(df)
    return result if result is not None else 0.0
