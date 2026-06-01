"""Pure fund NAV and risk-return metric helpers."""

from __future__ import annotations

from typing import Any

from src.schemas.fund import NavPoint
from src.tools.quant.metrics import (
    calculate_max_drawdown,
    calculate_sharpe,
    calculate_sortino,
    calculate_volatility,
)


def normalize_nav_history(raw: Any) -> list[NavPoint]:
    """Normalize host-provided NAV history into chronological NavPoint values."""
    if raw is None:
        return []

    records: list[Any]
    if isinstance(raw, dict):
        records = [
            {"date": date, "nav": value}
            for date, value in raw.items()
        ]
    elif isinstance(raw, list):
        records = raw
    else:
        return []

    points: list[NavPoint] = []
    for item in records:
        point = _nav_point_from_item(item)
        if point is not None:
            points.append(point)

    return sorted(points, key=lambda point: point.date)


def calculate_returns_from_nav(nav_history: Any) -> list[float]:
    """Calculate period returns from NAV points.

    If a point carries an explicit ``daily_return`` value, that value is used
    for that point. Otherwise the return is calculated from adjacent NAV values.
    """
    points = normalize_nav_history(nav_history)
    if len(points) < 2:
        return []

    returns: list[float] = []
    previous = points[0]
    for point in points[1:]:
        if point.daily_return is not None:
            returns.append(float(point.daily_return))
        elif previous.nav > 0:
            returns.append((point.nav / previous.nav) - 1.0)
        previous = point
    return returns


def calculate_fund_metrics(nav_history: Any) -> dict[str, Any]:
    """Calculate deterministic fund risk-return metrics from NAV history."""
    points = normalize_nav_history(nav_history)
    returns = calculate_returns_from_nav(points)
    nav_values = [point.nav for point in points]

    total_return = 0.0
    if len(nav_values) >= 2 and nav_values[0] > 0:
        total_return = (nav_values[-1] / nav_values[0]) - 1.0

    return_1m = calculate_period_return(points, 1)
    return_3m = calculate_period_return(points, 3)
    return_6m = calculate_period_return(points, 6)
    return_1y = calculate_period_return(points, 12)

    momentum_values = [v for v in (return_1m, return_3m, return_6m) if v is not None]
    recent_momentum = round(sum(momentum_values) / len(momentum_values), 6) if momentum_values else 0.0

    annualized_volatility = calculate_volatility(returns)
    risk_adjusted_score = round(recent_momentum / annualized_volatility, 6) if annualized_volatility > 0 else 0.0

    rolling_drawdown = calculate_rolling_drawdown(points)

    return {
        "observation_count": len(points),
        "return_count": len(returns),
        "total_return": round(total_return, 6),
        "annualized_volatility": round(annualized_volatility, 6),
        "max_drawdown": round(calculate_max_drawdown(nav_values), 6),
        "sharpe": round(calculate_sharpe(returns), 6),
        "sortino": round(calculate_sortino(returns), 6),
        "return_1m": return_1m,
        "return_3m": return_3m,
        "return_6m": return_6m,
        "return_1y": return_1y,
        "recent_momentum": recent_momentum,
        "risk_adjusted_score": risk_adjusted_score,
        "rolling_drawdown": rolling_drawdown,
    }


def _nav_point_from_item(item: Any) -> NavPoint | None:
    if isinstance(item, NavPoint):
        return item
    if isinstance(item, (int, float)):
        return None
    if not isinstance(item, dict):
        return None

    date = item.get("date")
    nav = item.get("nav")
    if date is None or nav is None:
        return None

    try:
        return NavPoint(
            date=str(date),
            nav=float(nav),
            accumulated_nav=_optional_float(item.get("accumulated_nav")),
            daily_return=_optional_float(item.get("daily_return")),
        )
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_period_return(nav_history: list[NavPoint], months: int) -> float | None:
    """Calculate return for a given lookback period in months."""
    if not nav_history or len(nav_history) < 2:
        return None
    target = nav_history[-1].date
    cutoff = _offset_date(target, -months)
    start_nav = None
    for np in nav_history:
        if np.date <= cutoff:
            start_nav = np.nav
        else:
            break
    if start_nav is None:
        start_nav = nav_history[0].nav
    end_nav = nav_history[-1].nav
    if start_nav <= 0:
        return None
    return round((end_nav / start_nav) - 1.0, 6)


def calculate_rolling_drawdown(nav_history: list[NavPoint], window: int | None = None) -> dict[str, Any]:
    """Calculate rolling max drawdown from NAV history."""
    if not nav_history:
        return {"max_drawdown": 0.0, "peak_nav": None, "trough_nav": None}
    peak = nav_history[0].nav
    max_dd = 0.0
    trough = peak
    for np in nav_history:
        if np.nav > peak:
            peak = np.nav
        dd = (peak - np.nav) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            trough = np.nav
    return {"max_drawdown": round(max_dd, 6), "peak_nav": round(peak, 6), "trough_nav": round(trough, 6)}


def _offset_date(date_str: str, months: int) -> str:
    """Offset a date string by N months."""
    try:
        from datetime import date as dt
        from calendar import monthrange
        y, m, d = map(int, date_str.split("-")[:3])
        m += months
        while m > 12:
            y += 1; m -= 12
        while m < 1:
            y -= 1; m += 12
        last_day = monthrange(y, m)[1]
        d = min(d, last_day)
        return f"{y:04d}-{m:02d}-{d:02d}"
    except (ValueError, TypeError):
        return date_str
