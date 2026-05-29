"""Compose sub-agent opinions into the agent_decisions.v2 contract."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from legacy.agents.protocols import AgentOpinion


def compose_agent_decisions(
    evidence: Mapping[str, Any],
    opinions: Iterable[AgentOpinion],
) -> dict[str, Any]:
    """Compose news/scoring/portfolio opinions into `agent_decisions.v2`.

    This is a deterministic contract composer for tests and future LLM runners.
    It does not invent missing decisions; required fund scoring opinions must be
    provided by a scoring agent.
    """
    opinions_by_agent: dict[str, list[Mapping[str, Any]]] = {}
    for opinion in opinions:
        opinions_by_agent.setdefault(opinion.agent, []).append(opinion.payload)

    portfolio_opinion = _first(opinions_by_agent.get("portfolio"))
    scoring_by_code = {
        str(payload.get("fund_code")): payload
        for payload in opinions_by_agent.get("scoring", [])
        if payload.get("fund_code")
    }
    news_by_code = {
        str(payload.get("fund_code")): payload
        for payload in opinions_by_agent.get("news", [])
        if payload.get("fund_code")
    }

    funds = evidence.get("funds") or {}
    fund_scores = {}
    for code in funds:
        scoring = scoring_by_code.get(str(code))
        if not scoring:
            raise ValueError(f"缺少 scoring opinion: {code}")
        target = ((portfolio_opinion.get("fund_targets") or {}).get(str(code)) or {})
        fund_scores[str(code)] = _compose_fund_score(scoring, target)

    news = {
        code: _compose_news_decision(payload)
        for code, payload in news_by_code.items()
    }

    recommendations = portfolio_opinion.get("recommendations", [])
    if recommendations is None:
        recommendations = []

    return {
        "schema_version": "agent_decisions.v2",
        "evidence_report_date": evidence.get("report_date"),
        "portfolio": {
            "stance": portfolio_opinion.get("stance", "neutral"),
            "tldr": portfolio_opinion.get("tldr") or portfolio_opinion.get("summary") or "已完成子 Agent 综合研判",
            "risk_summary": portfolio_opinion.get("risk_summary", []),
            "execution_notes": portfolio_opinion.get("execution_notes", []),
            "daily_analysis": portfolio_opinion.get("daily_analysis", "子 Agent 已完成组合归因汇总。"),
        },
        "news": news,
        "fund_scores": fund_scores,
        "recommendations": recommendations,
    }


def _compose_fund_score(scoring: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    final_action = target.get("final_action") or scoring.get("final_action") or "hold"
    triggers = target.get("triggers") or scoring.get("triggers") or scoring.get("watch") or []
    rationale = scoring.get("rationale") or []
    if not rationale:
        raise ValueError(f"scoring opinion 缺少 rationale: {scoring.get('fund_code')}")
    if not triggers:
        raise ValueError(f"scoring/portfolio opinion 缺少 triggers: {scoring.get('fund_code')}")

    return {
        "agent_adjustments": scoring.get("agent_adjustments") or {},
        "final_scores": scoring.get("final_scores") or {},
        "final_action": final_action,
        "target_weight_pct": target.get("target_weight_pct", scoring.get("target_weight_pct")),
        "adjust_amount": target.get("adjust_amount", scoring.get("adjust_amount")),
        "suggested_stop_profit_pct": scoring.get("suggested_stop_profit_pct"),
        "suggested_stop_loss_pct": scoring.get("suggested_stop_loss_pct"),
        "daily_attribution": target.get("daily_attribution") or scoring.get("daily_attribution"),
        "rationale": rationale,
        "triggers": triggers,
        "trend_view": scoring.get("trend_view", ""),
    }


def _compose_news_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "summary": payload.get("summary", ""),
        "impact": payload.get("impact", "insufficient_evidence"),
        "relevance": payload.get("relevance", "insufficient_evidence"),
        "confidence": payload.get("confidence", 0.0),
        "watch": payload.get("watch", []),
        "key_news": payload.get("key_news", []),
    }


def _first(items: list[Mapping[str, Any]] | None) -> Mapping[str, Any]:
    if not items:
        raise ValueError("缺少 portfolio opinion")
    return items[0]
