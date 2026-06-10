"""Right-side confirmation diagnostics for FundAnalysisSkill.

Deterministic, local-only assessment of whether a rebound/confirmation
exists for funds that have experienced drawdown. This is NOT a trading
signal generator. It is an evidence readiness diagnostic.

Does NOT fetch data, call providers, use LLMs, or make formal decisions.
"""

from __future__ import annotations

from typing import Any

from .context import CoreMetricsBundle, PortfolioInputBundle
from .safe_parsing import _safe_float


REBOUND_THRESHOLD = 0.02
MATERIAL_DRAWDOWN_THRESHOLD = -0.03


def compute_right_side_confirmation_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    has_confirmed_right_side = False
    has_unconfirmed_rebound = False
    needs_more_evidence = False
    notes: list[str] = []

    nav_history = bundle.nav_history or {}
    benchmark_history = bundle.benchmark_history or {}
    fund_profiles = bundle.fund_profiles or {}
    raw_payload = bundle.payload or {}

    news_evidence = raw_payload.get("news_evidence") or raw_payload.get("recent_news") or []
    sentiment_evidence = raw_payload.get("sentiment_evidence") or raw_payload.get("sentiment_snapshot") or []

    for pos in bundle.positions:
        if not isinstance(pos, dict) or not pos.get("fund_code"):
            continue
        fund_code = str(pos["fund_code"])
        fund_name = str(pos.get("fund_name", pos.get("name", "")))

        fund_nav_series = nav_history.get(fund_code, [])
        profile = fund_profiles.get(fund_code, {}) if isinstance(fund_profiles, dict) else {}
        benchmark_id = str(profile.get("benchmark", "")) if isinstance(profile, dict) else ""
        bench_series = benchmark_history.get(fund_code, benchmark_history.get(benchmark_id, []))

        recent_drawdown_pct = _compute_drawdown(fund_nav_series)
        recent_rebound_pct = _compute_rebound(fund_nav_series)
        is_applicable = (
            recent_drawdown_pct is not None
            and recent_drawdown_pct <= MATERIAL_DRAWDOWN_THRESHOLD
        )

        nav_confirmation = _assess_nav_confirmation(fund_nav_series)
        benchmark_confirmation = _assess_benchmark_confirmation(bench_series)
        news_confirmation = _assess_news_confirmation(fund_code, news_evidence)
        sentiment_confirmation = _assess_sentiment_confirmation(fund_code, sentiment_evidence)

        missing_reason: list[str] = []
        recommended_next_data: list[str] = []

        if not isinstance(fund_nav_series, list) or not fund_nav_series:
            missing_reason.append("missing_nav_history")
            recommended_next_data.append("fund NAV history")
        if not isinstance(bench_series, list) or not bench_series:
            missing_reason.append("missing_benchmark_history")
            recommended_next_data.append("benchmark price history")
        if not news_evidence:
            missing_reason.append("missing_news_evidence")
            recommended_next_data.append("recent news evidence")
        if not sentiment_evidence:
            missing_reason.append("missing_sentiment_evidence")
            recommended_next_data.append("sentiment snapshot")

        applicability = "applicable" if is_applicable else "not_applicable"
        not_applicable_reason = "" if is_applicable else "no_material_drawdown"

        if is_applicable:
            right_side_confirmed = _determine_right_side_confirmed(
                nav_confirmation, benchmark_confirmation,
                news_confirmation, sentiment_confirmation,
            )

            evidence_state = _determine_evidence_state(
                nav_confirmation, benchmark_confirmation,
                news_confirmation, sentiment_confirmation,
            )
        else:
            right_side_confirmed = False
            evidence_state = "not_applicable"
            recommended_next_data = []

        if right_side_confirmed:
            has_confirmed_right_side = True
        elif is_applicable and nav_confirmation == "confirmed":
            has_unconfirmed_rebound = True
        if is_applicable and evidence_state in ("missing", "weak", "contradictory"):
            needs_more_evidence = True

        items.append({
            "fund_code": fund_code,
            "fund_name": fund_name,
            "recent_drawdown_pct": recent_drawdown_pct,
            "recent_rebound_pct": recent_rebound_pct,
            "benchmark_confirmation": benchmark_confirmation,
            "nav_confirmation": nav_confirmation,
            "news_confirmation": news_confirmation,
            "sentiment_confirmation": sentiment_confirmation,
            "right_side_confirmed": right_side_confirmed,
            "evidence_state": evidence_state,
            "applicability": applicability,
            "not_applicable_reason": not_applicable_reason,
            "missing_reason": missing_reason,
            "recommended_next_data": recommended_next_data,
        })

    return {
        "items": items,
        "summary": {
            "has_confirmed_right_side": has_confirmed_right_side,
            "has_unconfirmed_rebound": has_unconfirmed_rebound,
            "needs_more_evidence": needs_more_evidence,
            "notes": notes,
        },
    }


def _compute_drawdown(series: Any) -> float | None:
    if not isinstance(series, list) or len(series) < 2:
        return None
    navs = []
    for pt in series:
        v = _safe_float(pt.get("nav") if isinstance(pt, dict) else pt)
        if v is not None:
            navs.append(v)
    if len(navs) < 2:
        return None
    peak = navs[0]
    max_dd = 0.0
    for v in navs:
        if v > peak:
            peak = v
        dd = (v - peak) / peak if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd
    return round(max_dd, 6) if max_dd < 0 else None


def _compute_rebound(series: Any) -> float | None:
    if not isinstance(series, list) or len(series) < 2:
        return None
    navs = []
    for pt in series:
        v = _safe_float(pt.get("nav") if isinstance(pt, dict) else pt)
        if v is not None:
            navs.append(v)
    if len(navs) < 2:
        return None
    low = min(navs)
    last = navs[-1]
    if low <= 0:
        return None
    rebound = (last - low) / low
    return round(rebound, 6) if rebound > 0 else None


def _assess_nav_confirmation(series: Any) -> str:
    if not isinstance(series, list) or len(series) < 2:
        return "missing"
    navs = []
    for pt in series:
        v = _safe_float(pt.get("nav") if isinstance(pt, dict) else pt)
        if v is not None:
            navs.append(v)
    if len(navs) < 2:
        return "missing"
    low = min(navs)
    last = navs[-1]
    if low <= 0:
        return "unknown"
    rebound = (last - low) / low
    if rebound >= REBOUND_THRESHOLD:
        return "confirmed"
    if last < navs[-2] if len(navs) >= 2 else False:
        return "negative"
    return "mixed"


def _assess_benchmark_confirmation(series: Any) -> str:
    if not isinstance(series, list) or len(series) < 2:
        return "missing"
    navs = []
    for pt in series:
        v = _safe_float(pt.get("nav") if isinstance(pt, dict) else pt)
        if v is not None:
            navs.append(v)
    if len(navs) < 2:
        return "missing"
    low = min(navs)
    last = navs[-1]
    if low <= 0:
        return "unknown"
    rebound = (last - low) / low
    if rebound >= REBOUND_THRESHOLD:
        return "confirmed"
    if last < navs[-2] if len(navs) >= 2 else False:
        return "negative"
    return "mixed"


def _assess_news_confirmation(fund_code: str, news: Any) -> str:
    if not isinstance(news, list) or not news:
        return "missing"
    positive = 0
    negative = 0
    for item in news:
        if not isinstance(item, dict):
            continue
        fc = item.get("fund_code", "")
        if fc and fc != fund_code:
            continue
        label = str(item.get("sentiment", item.get("label", ""))).lower()
        if label in ("positive", "bullish", "supportive"):
            positive += 1
        elif label in ("negative", "bearish", "adverse"):
            negative += 1
    if positive > 0 and negative > 0:
        return "mixed"
    if positive > 0:
        return "confirmed"
    if negative > 0:
        return "negative"
    return "unknown"


def _assess_sentiment_confirmation(fund_code: str, sentiment: Any) -> str:
    if not isinstance(sentiment, list) or not sentiment:
        return "missing"
    positive = 0
    negative = 0
    for item in sentiment:
        if not isinstance(item, dict):
            continue
        fc = item.get("fund_code", "")
        if fc and fc != fund_code:
            continue
        label = str(item.get("sentiment", item.get("label", ""))).lower()
        score = _safe_float(item.get("score"))
        if label in ("positive", "bullish") or (score is not None and score > 0.3):
            positive += 1
        elif label in ("negative", "bearish") or (score is not None and score < -0.3):
            negative += 1
    if positive > 0 and negative > 0:
        return "mixed"
    if positive > 0:
        return "confirmed"
    if negative > 0:
        return "negative"
    return "unknown"


def _determine_right_side_confirmed(
    nav_confirmation: str,
    benchmark_confirmation: str,
    news_confirmation: str,
    sentiment_confirmation: str,
) -> bool:
    if nav_confirmation != "confirmed":
        return False
    if benchmark_confirmation == "negative":
        return False
    if news_confirmation == "negative":
        return False
    if sentiment_confirmation == "negative":
        return False
    confirmations = [nav_confirmation, benchmark_confirmation, news_confirmation, sentiment_confirmation]
    missing_count = sum(1 for c in confirmations if c == "missing")
    if missing_count >= 2:
        return False
    return True


def _determine_evidence_state(
    nav_confirmation: str,
    benchmark_confirmation: str,
    news_confirmation: str,
    sentiment_confirmation: str,
) -> str:
    confirmations = [nav_confirmation, benchmark_confirmation, news_confirmation, sentiment_confirmation]
    if any(c == "negative" for c in confirmations) and any(c == "confirmed" for c in confirmations):
        return "contradictory"
    missing_count = sum(1 for c in confirmations if c in ("missing",))
    if missing_count >= 2:
        return "missing"
    if missing_count == 1:
        return "weak"
    return "sufficient"
