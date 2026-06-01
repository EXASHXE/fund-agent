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


def calculate_fund_metrics(nav_history: Any) -> dict[str, float | int]:
    """Calculate deterministic fund risk-return metrics from NAV history."""
    points = normalize_nav_history(nav_history)
    returns = calculate_returns_from_nav(points)
    nav_values = [point.nav for point in points]

    total_return = 0.0
    if len(nav_values) >= 2 and nav_values[0] > 0:
        total_return = (nav_values[-1] / nav_values[0]) - 1.0

    return {
        "observation_count": len(points),
        "return_count": len(returns),
        "total_return": round(total_return, 6),
        "annualized_volatility": round(calculate_volatility(returns), 6),
        "max_drawdown": round(calculate_max_drawdown(nav_values), 6),
        "sharpe": round(calculate_sharpe(returns), 6),
        "sortino": round(calculate_sortino(returns), 6),
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
