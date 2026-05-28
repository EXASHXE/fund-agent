"""Shared evidence and Agent decision contracts.

The CLI, services, and future Agent orchestrator all use this module as the
single validation boundary for report evidence and Agent-produced decisions.
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping, Sequence


def load_agent_decisions(
    path: str | None,
    report_date,
    scores: Sequence[Mapping[str, Any]] | None = None,
    news_data: Sequence[Mapping[str, Any]] | None = None,
    recommendation_candidates: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Load and reconcile Agent judgments with this run's evidence contract."""
    if not path:
        return None

    with open(path, "r", encoding="utf-8") as handle:
        decisions = json.load(handle)
    if decisions.get("schema_version") != "agent_decisions.v2":
        raise ValueError("Agent 决策 schema_version 必须为 agent_decisions.v2")
    decision_date = decisions.get("evidence_report_date")
    expected = report_date.isoformat()
    if decision_date != expected:
        raise ValueError(
            f"Agent 决策口径日 {decision_date or '缺失'} 与报告口径日 {expected} 不一致"
        )
    if not decisions.get("fund_scores"):
        raise ValueError("Agent 决策缺少 fund_scores，不能生成最终报告")
    portfolio = decisions.get("portfolio")
    if (
        not isinstance(portfolio, dict)
        or not portfolio.get("tldr")
        or not portfolio.get("stance")
        or not portfolio.get("daily_analysis")
    ):
        raise ValueError("Agent 决策缺少 portfolio.tldr 或 portfolio.stance 或 portfolio.daily_analysis")
    if not isinstance(decisions.get("recommendations"), list):
        raise ValueError("Agent 决策必须显式提供 recommendations 数组（允许为空）")

    score_lookup = {str(item.get("fund_code", "")): item for item in (scores or [])}
    missing_funds = sorted(set(score_lookup) - set(decisions["fund_scores"]))
    if missing_funds:
        raise ValueError(f"Agent 决策未覆盖全部评分基金: {', '.join(missing_funds)}")
    for code, baseline in score_lookup.items():
        _validate_fund_decision(code, baseline, decisions["fund_scores"].get(code))

    total_abs_adjust = sum(
        abs(adj)
        for decision in decisions["fund_scores"].values()
        for adj in decision.get("agent_adjustments", {}).values()
        if isinstance(adj, (int, float))
    )
    if total_abs_adjust == 0:
        raise ValueError(
            "所有基金的 Agent 调整评分均未触发（全为 0），不符合投研决策要求。"
            "请根据重大新闻、趋势或持仓风险给出至少一个非零调整，并在 rationale 中解释说明。"
        )

    target_sum = sum(
        decision.get("target_weight_pct")
        for decision in decisions["fund_scores"].values()
        if isinstance(decision.get("target_weight_pct"), (int, float))
    )
    if target_sum > 100 + 1e-6:
        raise ValueError(f"Agent 目标配置合计超过 100%: {target_sum:.2f}%")

    news_codes = {
        str(item.get("fund_code", "")) for item in (news_data or []) if item.get("fund_code")
    }
    missing_news = sorted(news_codes - set(decisions.get("news") or {}))
    if missing_news:
        raise ValueError(f"Agent 决策未覆盖全部新闻研判对象: {', '.join(missing_news)}")
    for code in news_codes:
        _validate_news_decision(code, decisions["news"][code])

    candidate_codes = {
        str(item.get("code") or item.get("fund_code", ""))
        for item in (recommendation_candidates or [])
    }
    recommended_codes = {
        str(item.get("code") or item.get("fund_code", ""))
        for item in decisions["recommendations"]
    }
    if "" in recommended_codes:
        raise ValueError("Agent 推荐对象必须提供基金代码")
    unsupported = sorted(recommended_codes - candidate_codes)
    if unsupported:
        raise ValueError(f"Agent 最终推荐缺少本次候选证据: {', '.join(unsupported)}")
    return decisions


def build_report_evidence(
    report_date,
    scores: Sequence[Mapping[str, Any]] | None,
    holdings_data: Mapping[str, Any] | None,
    news_data: Sequence[Mapping[str, Any]] | None,
    correlations,
    stress_results: Sequence[Mapping[str, Any]] | None,
    portfolio_risk_matrix: Mapping[str, Any] | None,
    recommendations: Sequence[Mapping[str, Any]] | None = None,
    recommendation_status: str = "skipped",
    workflow_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build serializable evidence consumed by the fund-analyst Agent."""
    by_fund = (holdings_data or {}).get("by_fund", {})
    funds = {}
    daily_clues = {}

    for score in scores or []:
        code = score.get("fund_code")
        metrics = by_fund.get(code, {})
        news = next((item for item in (news_data or []) if item.get("fund_code") == code), {})
        funds[code] = {
            "identity": {
                "code": code,
                "name": score.get("fund_name"),
                "fund_type": score.get("fund_type"),
                "data_completeness": score.get("data_completeness"),
            },
            "holding_metrics": metrics,
            "quant_baseline": {
                "macro_score": score.get("macro_score"),
                "meso_score": score.get("meso_score"),
                "micro_score": score.get("micro_score"),
                "total_score": score.get("composite_score"),
                "score_confidence": score.get("score_confidence"),
            },
            "factor_matrix": score.get("factor_matrix") or {},
            "trend_evidence": score.get("trend_evidence") or {},
            "risk_constraints": score.get("risk_constraints") or {},
            "news_evidence": {
                "news_count": news.get("news_count", 0),
                "decayed_lexicon_signal": news.get("sentiment_mean"),
                "brief": news.get("brief") or {},
                "evaluation": news.get("news_evaluation") or {},
                "samples": (news.get("news_list") or [])[:10],
                "post_cutoff_news": news.get("post_cutoff_news") or [],
                "relevance_task": news.get("relevance_task") or {},
            },
        }

        daily_clues[code] = {
            "fund_name": score.get("fund_name"),
            "day_profit": metrics.get("day_profit"),
            "day_return_pct": metrics.get("day_return_pct"),
            "top_news_headlines": [n.get("title") for n in (news.get("news_list") or [])[:5]],
        }

    corr_payload = correlations.to_dict() if hasattr(correlations, "to_dict") else {}
    return {
        "schema_version": "report_evidence.v2",
        "report_date": report_date.isoformat(),
        "report_status": "awaiting_agent_decisions",
        "portfolio": {
            "total_value": (holdings_data or {}).get("total_value", 0),
            "total_cost": (holdings_data or {}).get("total_cost", 0),
            "total_profit": (holdings_data or {}).get("total_profit", 0),
            "daily_profit": (holdings_data or {}).get("total_day_profit", 0),
            "daily_return_pct": (holdings_data or {}).get("total_day_return_pct", 0),
            "daily_attribution_clues": daily_clues,
        },
        "funds": funds,
        "portfolio_evidence": {
            "correlations": corr_payload,
            "stress_tests": stress_results or [],
            "risk_matrix": portfolio_risk_matrix or {},
        },
        "workflow_evidence": {
            "dca_rows": (workflow_context or {}).get("dca_rows") or [],
            "settlement_rows": (workflow_context or {}).get("settlement_rows") or [],
            "top_news": (workflow_context or {}).get("top_news") or [],
        },
        "recommendation_evidence": {
            "status": recommendation_status,
            "candidates": recommendations or [],
        },
    }


def write_report_evidence(output_path: str, evidence: Mapping[str, Any]) -> str:
    """Write a sibling `.evidence.json` file for an intended report path."""
    base, ext = os.path.splitext(output_path)
    if base.endswith(".evidence"):
        base = base[:-9]
    path = f"{base}.evidence.json" if ext else f"{output_path}.evidence.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, ensure_ascii=False, indent=2, default=str)
    return path


def _validate_fund_decision(code: str, baseline: Mapping[str, Any], decision: Any) -> None:
    if not isinstance(decision, dict):
        raise ValueError(f"Agent 基金决策缺失或格式错误: {code}")
    final_scores = decision.get("final_scores")
    adjustments = decision.get("agent_adjustments")
    if not isinstance(final_scores, dict) or not isinstance(adjustments, dict):
        raise ValueError(f"Agent 基金决策缺少 final_scores/agent_adjustments: {code}")

    baseline_keys = {"macro": "macro_score", "meso": "meso_score", "micro": "micro_score"}
    for dimension, baseline_key in baseline_keys.items():
        final = final_scores.get(dimension)
        adjustment = adjustments.get(dimension)
        if not isinstance(final, (int, float)) or not isinstance(adjustment, (int, float)):
            raise ValueError(f"Agent 基金决策分项必须为数值: {code}.{dimension}")
        if not -10 <= adjustment <= 10:
            raise ValueError(f"Agent 调整分超出 [-10, +10]: {code}.{dimension}")
        base = baseline.get(baseline_key)
        if isinstance(base, (int, float)) and abs(final - (base + adjustment)) > 1e-6:
            raise ValueError(f"Agent 最终分无法与量化基准及调整分对账: {code}.{dimension}")

    final_total = final_scores.get("total")
    calculated_total = sum(final_scores[key] for key in ("macro", "meso", "micro"))
    if not isinstance(final_total, (int, float)) or abs(final_total - calculated_total) > 1e-6:
        raise ValueError(f"Agent 综合分无法与分项合计对账: {code}")
    if not 0 <= final_total <= 100:
        raise ValueError(f"Agent 综合分超出 [0, 100]: {code}")
    if not decision.get("final_action"):
        raise ValueError(f"Agent 基金决策缺少 final_action: {code}")
    if not isinstance(decision.get("rationale"), list) or not decision["rationale"]:
        raise ValueError(f"Agent 基金决策缺少 rationale: {code}")
    if not isinstance(decision.get("triggers"), list) or not decision["triggers"]:
        raise ValueError(f"Agent 基金决策缺少 triggers: {code}")
    for field in ("target_weight_pct", "adjust_amount"):
        if field not in decision:
            raise ValueError(f"Agent 基金决策缺少 {field}: {code}")
    target = decision.get("target_weight_pct")
    if target is not None and (not isinstance(target, (int, float)) or not 0 <= target <= 100):
        raise ValueError(f"Agent 目标占比超出 [0, 100]: {code}")

    for pct_field in ("suggested_stop_profit_pct", "suggested_stop_loss_pct"):
        val = decision.get(pct_field)
        if val is not None and not isinstance(val, (int, float)):
            raise ValueError(f"Agent {pct_field} 必须为数值: {code}")

    if decision.get("daily_attribution") is not None and not isinstance(decision.get("daily_attribution"), str):
        raise ValueError(f"Agent daily_attribution 必须为字符串: {code}")


def _validate_news_decision(code: str, decision: Any) -> None:
    if not isinstance(decision, dict):
        raise ValueError(f"Agent 新闻研判缺失或格式错误: {code}")
    for field in ("summary", "impact", "relevance"):
        if not decision.get(field):
            raise ValueError(f"Agent 新闻研判缺少 {field}: {code}")
    confidence = decision.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError(f"Agent 新闻研判置信度必须在 [0, 1]: {code}")
    if "key_news" in decision:
        if not isinstance(decision["key_news"], list):
            raise ValueError(f"Agent 新闻研判 key_news 必须为列表: {code}")
        for item in decision["key_news"]:
            if not isinstance(item, dict) or "title" not in item or "reason" not in item:
                raise ValueError(f"Agent 新闻研判 key_news 内项目必须包含 title 和 reason: {code}")
