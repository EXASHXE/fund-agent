"""Scoring evidence enrichment service."""

from __future__ import annotations


def attach_score_trends(store, scores):
    """Attach previous score and peak drawdown from saved snapshots."""
    for score in scores:
        history = store.get_fund_score_history(score["fund_code"], limit=50)
        valid_scores = [
            item.get("composite_score")
            for item in history
            if item.get("composite_score") is not None
        ]
        if not valid_scores:
            score["previous_score"] = None
            score["score_delta"] = None
            score["peak_score"] = score["composite_score"]
            score["drop_from_peak"] = 0
            continue

        previous = valid_scores[0]
        peak = max(valid_scores + [score["composite_score"]])
        score["previous_score"] = previous
        score["score_delta"] = score["composite_score"] - previous
        score["peak_score"] = peak
        score["drop_from_peak"] = peak - score["composite_score"]


def attach_decision_evidence(scores, news_contexts, holdings_data):
    """Attach trend and position evidence without publishing an automatic action."""
    from src.forecast.engine import build_trend_matrix

    total_value = (holdings_data or {}).get("total_value", 0) or 0
    by_fund = (holdings_data or {}).get("by_fund", {}) or {}
    for score in scores:
        code = score.get("fund_code")
        trend = build_trend_matrix(score, news_contexts.get(code, {}))
        detail = by_fund.get(code, {}) or {}
        current_value = float(detail.get("current_value", 0) or 0)
        current_weight = current_value / total_value if total_value else 0.0
        score["trend_evidence"] = trend
        score["risk_constraints"] = {
            "current_weight": round(current_weight, 4),
            "pending_amount": float(detail.get("pending_amount", 0) or 0),
            "is_qdii": int(detail.get("settle_delay", 1) or 1) >= 2
            or "QDII" in str(score.get("fund_type", "")).upper(),
            "dca_enabled": bool(detail.get("dca_enabled")),
            "requires_agent_decision": True,
        }
