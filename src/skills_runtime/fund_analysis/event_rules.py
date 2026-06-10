"""Event hype failure diagnostics for FundAnalysisSkill.

Deterministic, local-only detection of scenarios where a user expected a
positive catalyst/event, but post-event price/NAV/news reaction suggests
the hype failed. Does NOT fetch data, call providers, use LLMs, or make
formal decisions. suggested_analysis_action is always analysis-only.
"""

from __future__ import annotations

from typing import Any

from .context import CoreMetricsBundle, PortfolioInputBundle
from .safe_parsing import _safe_float


def compute_event_hype_failure_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    has_event_hype_failure = False
    high_risk_events: list[str] = []
    notes: list[str] = []

    raw_payload = bundle.payload or {}
    nav_history = bundle.nav_history or {}
    benchmark_history = bundle.benchmark_history or {}

    events = raw_payload.get("events") or raw_payload.get("catalyst_events") or raw_payload.get("event_metadata") or []
    news_evidence = raw_payload.get("news_evidence") or raw_payload.get("recent_news") or []

    if not isinstance(events, list) or not events:
        return {
            "items": [],
            "summary": {
                "has_event_hype_failure": False,
                "high_risk_events": [],
                "notes": ["no event metadata provided by host"],
            },
        }

    for event in events:
        if not isinstance(event, dict):
            continue
        event_name = str(event.get("event_name", event.get("name", "")))
        fund_code = str(event.get("fund_code", ""))
        expected_positive_catalyst = str(event.get("expected_positive_catalyst", ""))
        expected_direction = str(event.get("expected_direction", "")).lower()

        if not event_name or not fund_code:
            continue
        if expected_direction != "positive" and not expected_positive_catalyst:
            continue

        fund_name = ""
        for pos in bundle.positions:
            if isinstance(pos, dict) and pos.get("fund_code") == fund_code:
                fund_name = str(pos.get("fund_name", pos.get("name", "")))
                break

        event_date = str(event.get("event_date", ""))
        post_event_return_pct = _compute_post_event_return(fund_code, event_date, nav_history)
        bench_post_event_return_pct = _compute_post_event_benchmark_return(fund_code, event_date, benchmark_history)

        price_reaction = _classify_price_reaction(post_event_return_pct)
        news_reaction = _classify_news_reaction(fund_code, news_evidence)

        hype_failed = _determine_hype_failed(expected_positive_catalyst, expected_direction, price_reaction, news_reaction)
        risk_level = _classify_risk_level(hype_failed, post_event_return_pct)
        evidence_state = _classify_evidence_state(post_event_return_pct, news_reaction)
        suggested_action = _suggest_action(hype_failed, evidence_state)

        if hype_failed:
            has_event_hype_failure = True
        if risk_level == "high":
            high_risk_events.append(f"{event_name}:{fund_code}")

        items.append({
            "event_name": event_name,
            "fund_code": fund_code,
            "fund_name": fund_name,
            "expected_positive_catalyst": expected_positive_catalyst,
            "post_event_return_pct": post_event_return_pct,
            "benchmark_post_event_return_pct": bench_post_event_return_pct,
            "news_reaction": news_reaction,
            "price_reaction": price_reaction,
            "hype_failed": hype_failed,
            "risk_level": risk_level,
            "evidence_state": evidence_state,
            "missing_reason": _get_missing_reasons(post_event_return_pct, news_reaction),
            "suggested_analysis_action": suggested_action,
        })

    return {
        "items": items,
        "summary": {
            "has_event_hype_failure": has_event_hype_failure,
            "high_risk_events": high_risk_events,
            "notes": notes,
        },
    }


def _compute_post_event_return(
    fund_code: str,
    event_date: str,
    nav_history: Any,
) -> float | None:
    if not isinstance(nav_history, dict):
        return None
    series = nav_history.get(fund_code, [])
    if not isinstance(series, list) or not series or not event_date:
        return None

    pre_nav = None
    post_nav = None
    found_event = False
    for pt in series:
        if not isinstance(pt, dict):
            continue
        pt_date = str(pt.get("date", ""))
        pt_nav = _safe_float(pt.get("nav"))
        if pt_nav is None:
            continue
        if pt_date <= event_date:
            pre_nav = pt_nav
        if pt_date >= event_date:
            found_event = True
            post_nav = pt_nav

    if not found_event or pre_nav is None or post_nav is None or pre_nav == 0:
        return None
    return round(post_nav / pre_nav - 1, 6)


def _compute_post_event_benchmark_return(
    fund_code: str,
    event_date: str,
    benchmark_history: Any,
) -> float | None:
    if not isinstance(benchmark_history, dict):
        return None
    series = benchmark_history.get(fund_code, [])
    if not isinstance(series, list) or not series or not event_date:
        return None

    pre_nav = None
    post_nav = None
    found_event = False
    for pt in series:
        if not isinstance(pt, dict):
            continue
        pt_date = str(pt.get("date", ""))
        pt_nav = _safe_float(pt.get("nav"))
        if pt_nav is None:
            continue
        if pt_date <= event_date:
            pre_nav = pt_nav
        if pt_date >= event_date:
            found_event = True
            post_nav = pt_nav

    if not found_event or pre_nav is None or post_nav is None or pre_nav == 0:
        return None
    return round(post_nav / pre_nav - 1, 6)


def _classify_price_reaction(post_event_return: float | None) -> str:
    if post_event_return is None:
        return "missing"
    if post_event_return > 0.01:
        return "positive"
    if post_event_return < -0.01:
        return "negative"
    return "weak"


def _classify_news_reaction(fund_code: str, news: Any) -> str:
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
        return "positive"
    if negative > 0:
        return "negative"
    return "unknown"


def _determine_hype_failed(
    expected_positive_catalyst: str,
    expected_direction: str,
    price_reaction: str,
    news_reaction: str,
) -> bool:
    has_positive_expectation = expected_direction == "positive" or bool(expected_positive_catalyst)
    if not has_positive_expectation:
        return False
    if price_reaction == "missing":
        return False
    if price_reaction in ("weak", "negative"):
        if news_reaction not in ("positive",):
            return True
    return False


def _classify_risk_level(hype_failed: bool, post_event_return: float | None) -> str:
    if not hype_failed:
        return "low"
    if post_event_return is not None and post_event_return <= -0.03:
        return "high"
    if post_event_return is None:
        return "unknown"
    return "medium"


def _classify_evidence_state(
    post_event_return: float | None,
    news_reaction: str,
) -> str:
    if post_event_return is None and news_reaction == "missing":
        return "missing"
    if post_event_return is None or news_reaction == "missing":
        return "weak"
    if post_event_return is not None and news_reaction in ("positive", "negative", "mixed"):
        return "sufficient"
    return "weak"


def _suggest_action(hype_failed: bool, evidence_state: str) -> str:
    if evidence_state in ("missing", "weak"):
        return "data_needed"
    if hype_failed:
        return "reduce_hype_weight"
    return "watch"


def _get_missing_reasons(
    post_event_return: float | None,
    news_reaction: str,
) -> list[str]:
    reasons: list[str] = []
    if post_event_return is None:
        reasons.append("missing_nav_history")
    if news_reaction == "missing":
        reasons.append("missing_news_evidence")
    return reasons
