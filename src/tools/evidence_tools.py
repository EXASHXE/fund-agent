"""Read-only compressed evidence tools for Agent sub-tasks."""

from __future__ import annotations

from typing import Any, Mapping

from src.tools.registry import ToolRegistry


def build_evidence_tool_registry(evidence: Mapping[str, Any]) -> ToolRegistry:
    """Bind report_evidence slices as read-only Agent tools."""
    registry = ToolRegistry()

    @registry.tool(
        "evidence.fund_identity",
        "Return one fund's identity and risk constraints from report evidence.",
        agents=("news", "scoring", "portfolio", "strategy", "summary"),
    )
    def fund_identity(code: str):
        fund = _fund(evidence, code)
        return {
            "code": code,
            "identity": fund.get("identity") or {},
            "risk_constraints": fund.get("risk_constraints") or {},
            "holding_metrics": _compact_mapping(
                fund.get("holding_metrics") or {},
                ("current_value", "profit", "return_pct", "pending_amount", "nav_date"),
            ),
        }

    @registry.tool(
        "news.compressed_context",
        "Return compressed news evidence for one fund.",
        agents=("news", "summary"),
    )
    def news_context(code: str):
        news = (_fund(evidence, code).get("news_evidence") or {})
        evaluation = news.get("evaluation") or {}
        samples = []
        for item in (news.get("samples") or [])[:5]:
            samples.append(_compact_mapping(
                item,
                ("date", "title", "source", "matched_terms", "sentiment_score"),
            ))
        return {
            "code": code,
            "news_count": news.get("news_count", 0),
            "decayed_lexicon_signal": news.get("decayed_lexicon_signal"),
            "brief": news.get("brief") or {},
            "evaluation": _compact_mapping(
                evaluation,
                (
                    "quality_score",
                    "holding_coverage_count",
                    "holding_coverage_pct",
                    "coverage_warning",
                ),
            ),
            "samples": samples,
            "relevance_task": _compact_relevance_task(news.get("relevance_task") or {}),
        }

    @registry.tool(
        "scoring.factor_matrix",
        "Return quant baseline and explainable factor matrix for one fund.",
        agents=("scoring", "strategy", "summary"),
    )
    def scoring_context(code: str):
        fund = _fund(evidence, code)
        return {
            "code": code,
            "quant_baseline": fund.get("quant_baseline") or {},
            "factor_matrix": fund.get("factor_matrix") or {},
            "trend_evidence": fund.get("trend_evidence") or {},
        }

    @registry.tool(
        "portfolio.context",
        "Return portfolio-level risk, workflow, and attribution evidence.",
        agents=("portfolio", "strategy", "summary"),
    )
    def portfolio_context():
        return {
            "portfolio": evidence.get("portfolio") or {},
            "portfolio_evidence": evidence.get("portfolio_evidence") or {},
            "workflow_evidence": evidence.get("workflow_evidence") or {},
        }

    @registry.tool(
        "kg.snapshot",
        "Return KG exposure and impact-chain evidence from agent-enhanced reports.",
        agents=("news", "scoring", "portfolio", "strategy", "summary", "research"),
    )
    def kg_snapshot(code: str | None = None):
        snapshot = evidence.get("kg_snapshot") or {}
        if not code:
            return snapshot
        return {
            "fund_exposure": (
                (snapshot.get("fund_exposure") or {}).get(str(code), {})
            ),
            "impact_chains": snapshot.get("impact_chains") or {},
        }

    @registry.tool(
        "news.agent_evidence",
        "Return classified news, research summaries, and extracted events for one fund.",
        agents=("news", "scoring", "strategy", "summary", "research"),
    )
    def agent_news_evidence(code: str):
        news = (evidence.get("news_evidence") or {}).get(str(code), {})
        return {
            "classified_news": _compact_sequence(news.get("classified_news") or [], 20),
            "research_summaries": _compact_sequence(news.get("research_summaries") or [], 10),
            "extracted_events": _compact_sequence(news.get("extracted_events") or [], 20),
        }

    @registry.tool(
        "scoring.agent_evidence",
        "Return five-dimension ScoreEngine and LangGraph score evidence for one fund.",
        agents=("scoring", "strategy", "summary", "research"),
    )
    def agent_score_evidence(code: str):
        return (evidence.get("score_evidence") or {}).get(str(code), {})

    @registry.tool(
        "strategy.evidence",
        "Return StrategyEngine or StrategyAgent evidence for one fund.",
        agents=("strategy", "summary"),
    )
    def strategy_evidence(code: str):
        strategy = (evidence.get("strategy_evidence") or {}).get(str(code))
        if strategy:
            return strategy
        return _fund(evidence, code).get("strategy_advice") or {}

    @registry.tool(
        "recommendations.candidates",
        "Return Agent-reviewable recommendation candidates.",
        agents=("portfolio", "summary"),
    )
    def recommendation_candidates():
        recs = evidence.get("recommendation_evidence") or {}
        return {
            "status": recs.get("status", "skipped"),
            "candidates": [
                _compact_mapping(item, ("code", "fund_code", "name", "fund_name", "theme", "score", "reason"))
                for item in (recs.get("candidates") or [])[:10]
            ],
        }

    return registry


def _fund(evidence: Mapping[str, Any], code: str) -> Mapping[str, Any]:
    return (evidence.get("funds") or {}).get(str(code), {})


def _compact_mapping(payload: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {
        key: payload.get(key)
        for key in keys
        if key in payload and payload.get(key) is not None
    }


def _compact_sequence(payload: Any, limit: int) -> list[Any]:
    if isinstance(payload, list):
        return payload[:limit]
    if isinstance(payload, tuple):
        return list(payload[:limit])
    if payload:
        return [payload]
    return []


def _compact_relevance_task(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": task.get("task"),
        "holdings": (task.get("holdings") or [])[:10],
        "candidate_news": [
            _compact_mapping(
                item,
                ("id", "date", "title", "source", "matched_terms", "rule_relevance"),
            )
            for item in (task.get("candidate_news") or [])[:10]
        ],
    }
