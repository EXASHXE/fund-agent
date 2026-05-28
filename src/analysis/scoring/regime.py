"""Market regime detection from NAV volatility and event density."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import numpy as np

from src.analysis.scoring.types import MarketRegime


def compute_rolling_volatility(nav_series: list[float], window: int = 20) -> float:
    """Compute rolling realized volatility (annualized) from NAV series.

    Uses daily log returns, annualized by sqrt(252).
    Falls back to full-series vol if fewer than window data points.
    """
    if not nav_series or len(nav_series) < 3:
        return 0.0

    prices = np.array(nav_series, dtype=float)
    # Daily log returns
    returns = np.diff(np.log(prices[prices > 0] if np.all(prices > 0) else prices + 1e-12))
    if len(returns) < 2:
        return 0.0

    # Use recent window or full series
    recent = returns[-min(window, len(returns)):]
    if len(recent) < 2:
        return 0.0

    daily_vol = np.std(recent, ddof=1)
    annualized = daily_vol * math.sqrt(252)
    return round(float(annualized), 6)


def has_trend(nav_series: list[float], window: int = 60) -> bool:
    """Detect a directional trend using linear regression R² on recent data."""
    min_points = 30
    if not nav_series or len(nav_series) < min_points:
        return False

    recent = nav_series[-min(len(nav_series), window):]
    if len(recent) < min_points:
        return False

    y = np.array(recent, dtype=float)
    x = np.arange(len(y), dtype=float)

    # Simple linear regression: R²
    mean_y = np.mean(y)
    ss_tot = np.sum((y - mean_y) ** 2)
    if ss_tot < 1e-12:
        return False

    slope = np.sum((x - np.mean(x)) * (y - mean_y)) / np.sum((x - np.mean(x)) ** 2)
    intercept = mean_y - slope * np.mean(x)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    r_squared = 1.0 - ss_res / ss_tot

    # Strong trend: R² >= 0.7 with consistent direction
    return bool(r_squared >= 0.7)


def has_black_swan(events: list[dict]) -> bool:
    """Check if any event is a black swan or market crash."""
    if not events:
        return False
    for evt in events:
        evt_type = (evt.get("type") or "").lower()
        if evt_type in ("black_swan", "market_crash"):
            return True
        polarity = evt.get("polarity", 0) or 0
        magnitude = evt.get("magnitude", 0) or 0
        if abs(polarity) >= 0.85 and abs(magnitude) >= 0.85:
                return True
    return False


def count_high_magnitude_events(events: list[dict], days: int = 7, threshold: float = 0.6) -> int:
    """Count events with magnitude >= threshold in the last `days` days."""
    if not events:
        return 0

    cutoff = None
    # Try to get reference date from events or use today
    today = date.today()

    # Find the latest event date to use as reference
    latest_date = today
    for evt in events:
        dt_str = evt.get("date")
        if dt_str:
            try:
                d = datetime.strptime(str(dt_str)[:10], "%Y-%m-%d").date()
                if d > latest_date:
                    latest_date = d
            except (ValueError, TypeError):
                pass

    cutoff = latest_date - timedelta(days=days)

    count = 0
    for evt in events:
        mag = evt.get("magnitude", 0) or 0
        if mag < threshold:
            continue
        dt_str = evt.get("date")
        if dt_str:
            try:
                d = datetime.strptime(str(dt_str)[:10], "%Y-%m-%d").date()
                if d >= cutoff:
                    count += 1
            except (ValueError, TypeError):
                count += 1  # No date → count anyway
        else:
            count += 1  # No date → count anyway
    return count


def detect_regime(
    nav_series: list[float],
    events: list[dict],
    vol_window: int = 20,
    vol_threshold_high: float = 2.0,
    vol_threshold_low: float = 0.5,
    event_density_threshold_high: int = 3,
    event_density_threshold_crisis: int = 5,
) -> MarketRegime:
    """Detect current market regime from NAV volatility and event density.

    Decision logic:
    - CRISIS: event_density > 5 OR has_black_swan (CRISIS checked FIRST)
    - HIGH_VOLATILITY: recent_vol > 2× historical_avg OR event_density > 3
    - TRENDING: recent_vol < 0.5× historical_avg AND has_trend
    - NORMAL: default
    """
    if not nav_series or len(nav_series) < 2:
        return MarketRegime.NORMAL

    recent_vol = compute_rolling_volatility(nav_series, window=vol_window)

    # Historical vol: use FULL series (excluding recent window) for baseline comparison
    full_window = len(nav_series) - vol_window if len(nav_series) > vol_window else len(nav_series)
    if full_window <= 0:
        full_window = len(nav_series)
    # Use the EARLIER portion (not the recent window) for historical comparison
    historical_series = nav_series[:len(nav_series) - vol_window] if len(nav_series) > vol_window else nav_series
    historical_avg_vol = compute_rolling_volatility(historical_series, window=max(9, full_window - 1)) if historical_series else 0.0
    if historical_avg_vol < 1e-12:
        historical_avg_vol = max(recent_vol * 0.5, 0.01) if recent_vol > 0 else 0.01

    event_density = count_high_magnitude_events(events, days=7, threshold=0.6)

    # Crisis check first (takes priority)
    if event_density > event_density_threshold_crisis or has_black_swan(events):
        return MarketRegime.CRISIS

    # High volatility: recent vol significantly exceeds historical OR absolute vol is very high
    high_vol_conditional = (
        recent_vol > vol_threshold_high * historical_avg_vol
        or recent_vol > 0.50  # Absolute threshold: > 50% annualized vol is always high
        or event_density > event_density_threshold_high
    )
    if high_vol_conditional:
        return MarketRegime.HIGH_VOLATILITY

    # Trending
    if recent_vol < vol_threshold_low * historical_avg_vol and has_trend(nav_series, window=60):
        return MarketRegime.TRENDING

    return MarketRegime.NORMAL
