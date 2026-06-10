"""Benchmark divergence diagnostics for FundAnalysisSkill.

Deterministic, local-only comparison of fund performance against
relevant benchmark movement. Does NOT fetch data, call providers,
use LLMs, or make formal decisions.
"""

from __future__ import annotations

from typing import Any

from .context import CoreMetricsBundle, PortfolioInputBundle
from .safe_parsing import _safe_float


def compute_benchmark_divergence_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    has_benchmark_divergence = False
    has_severe_underperformance = False
    severe_underperformers: list[str] = []
    notes: list[str] = []

    benchmark_history = bundle.benchmark_history or {}
    nav_history = bundle.nav_history or {}
    fund_profiles = bundle.fund_profiles or {}

    for pos in bundle.positions:
        if not isinstance(pos, dict) or not pos.get("fund_code"):
            continue
        fund_code = str(pos["fund_code"])
        fund_name = str(pos.get("fund_name", pos.get("name", "")))

        profile = fund_profiles.get(fund_code, {}) if isinstance(fund_profiles, dict) else {}
        benchmark_id = str(profile.get("benchmark", "")) if isinstance(profile, dict) else ""

        fund_nav_series = nav_history.get(fund_code, [])
        bench_series = benchmark_history.get(fund_code, benchmark_history.get(benchmark_id, []))

        if not isinstance(fund_nav_series, list) or not fund_nav_series:
            items.append({
                "fund_code": fund_code,
                "fund_name": fund_name,
                "benchmark_id": benchmark_id,
                "fund_return_pct": None,
                "benchmark_return_pct": None,
                "excess_return_pct": None,
                "divergence_level": "unknown",
                "divergence_direction": "unknown",
                "evidence_state": "missing",
                "missing_reason": ["missing_nav_history"],
                "lookback_days": 0,
            })
            continue

        if not isinstance(bench_series, list) or not bench_series:
            items.append({
                "fund_code": fund_code,
                "fund_name": fund_name,
                "benchmark_id": benchmark_id,
                "fund_return_pct": None,
                "benchmark_return_pct": None,
                "excess_return_pct": None,
                "divergence_level": "unknown",
                "divergence_direction": "unknown",
                "evidence_state": "missing",
                "missing_reason": ["missing_benchmark_history"],
                "lookback_days": 0,
            })
            notes.append(f"missing benchmark history for {fund_code}")
            continue

        fund_return_pct = _compute_return(fund_nav_series)
        bench_return_pct = _compute_return(bench_series)

        if fund_return_pct is None or bench_return_pct is None:
            items.append({
                "fund_code": fund_code,
                "fund_name": fund_name,
                "benchmark_id": benchmark_id,
                "fund_return_pct": fund_return_pct,
                "benchmark_return_pct": bench_return_pct,
                "excess_return_pct": None,
                "divergence_level": "unknown",
                "divergence_direction": "unknown",
                "evidence_state": "missing",
                "missing_reason": ["insufficient_data_points"],
                "lookback_days": 0,
            })
            continue

        excess_return_pct = round(fund_return_pct - bench_return_pct, 6)
        divergence_level = _classify_divergence(excess_return_pct)
        divergence_direction = _classify_direction(excess_return_pct)
        lookback_days = _compute_lookback_days(fund_nav_series)

        if divergence_level in ("moderate", "severe"):
            has_benchmark_divergence = True
        if divergence_level == "severe" and divergence_direction == "underperforming":
            has_severe_underperformance = True
            severe_underperformers.append(fund_code)

        items.append({
            "fund_code": fund_code,
            "fund_name": fund_name,
            "benchmark_id": benchmark_id,
            "fund_return_pct": round(fund_return_pct, 6),
            "benchmark_return_pct": round(bench_return_pct, 6),
            "excess_return_pct": excess_return_pct,
            "divergence_level": divergence_level,
            "divergence_direction": divergence_direction,
            "evidence_state": "sufficient",
            "missing_reason": [],
            "lookback_days": lookback_days,
        })

    return {
        "items": items,
        "summary": {
            "has_benchmark_divergence": has_benchmark_divergence,
            "has_severe_underperformance": has_severe_underperformance,
            "severe_underperformers": severe_underperformers,
            "notes": notes,
        },
    }


def _compute_return(series: list[Any]) -> float | None:
    if not isinstance(series, list) or len(series) < 2:
        return None
    first = series[0]
    last = series[-1]
    first_nav = _safe_float(first.get("nav") if isinstance(first, dict) else first)
    last_nav = _safe_float(last.get("nav") if isinstance(last, dict) else last)
    if first_nav is None or last_nav is None or first_nav == 0:
        return None
    return last_nav / first_nav - 1


def _classify_divergence(excess_return_pct: float) -> str:
    abs_excess = abs(excess_return_pct)
    if abs_excess >= 0.10:
        return "severe"
    if abs_excess >= 0.05:
        return "moderate"
    if abs_excess >= 0.02:
        return "mild"
    return "none"


def _classify_direction(excess_return_pct: float) -> str:
    if excess_return_pct > 0.02:
        return "outperforming"
    if excess_return_pct < -0.02:
        return "underperforming"
    return "in_line"


def _compute_lookback_days(series: list[Any]) -> int:
    if not isinstance(series, list) or len(series) < 2:
        return 0
    first = series[0]
    last = series[-1]
    if isinstance(first, dict) and isinstance(last, dict):
        first_date = str(first.get("date", ""))
        last_date = str(last.get("date", ""))
        try:
            from datetime import date
            d1 = date.fromisoformat(first_date)
            d2 = date.fromisoformat(last_date)
            return (d2 - d1).days
        except (ValueError, TypeError):
            pass
    return 0
