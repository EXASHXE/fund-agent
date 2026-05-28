from src.tools.evidence_tools import build_evidence_tool_registry


def _evidence():
    return {
        "portfolio": {"total_value": 10000},
        "portfolio_evidence": {"risk_matrix": {"warnings": ["集中"]}},
        "workflow_evidence": {"settlement_rows": [{"code": "000001"}]},
        "kg_snapshot": {
            "fund_exposure": {"000001": {"themes": ["消费"]}},
            "impact_chains": {"evt-1": {"paths": []}},
        },
        "news_evidence": {
            "000001": {
                "classified_news": [{"title": "分类新闻"}],
                "research_summaries": [{"what": "发生事件"}],
                "extracted_events": [{"id": "evt-1"}],
            },
        },
        "score_evidence": {
            "000001": {
                "regime": "normal",
                "quant_score": {"score": 72},
                "agent_state": {"final_score": 70},
            },
        },
        "strategy_evidence": {
            "000001": {"action": "hold", "confidence": 0.72},
        },
        "funds": {
            "000001": {
                "identity": {"name": "测试基金"},
                "holding_metrics": {"current_value": 1000, "ignored": "x"},
                "risk_constraints": {"current_weight": 0.1},
                "quant_baseline": {"macro_score": 15},
                "factor_matrix": {"macro": [{"name": "fund_type_cycle_fit"}]},
                "trend_evidence": {"short_term": {"direction": "flat"}},
                "news_evidence": {
                    "news_count": 2,
                    "brief": {"summary": "压缩摘要"},
                    "evaluation": {
                        "quality_score": 0.8,
                        "coverage_warning": "覆盖偏窄",
                        "raw_extra": "drop",
                    },
                    "samples": [
                        {"date": "2026-05-22", "title": "新闻A", "content": "long text"},
                        {"date": "2026-05-21", "title": "新闻B", "content": "long text"},
                    ],
                    "relevance_task": {
                        "holdings": [{"name": "重仓A"}],
                        "candidate_news": [{"id": 1, "title": "候选", "content": "drop"}],
                    },
                },
            }
        },
        "recommendation_evidence": {
            "status": "ok",
            "candidates": [{"code": "588710", "name": "半导体ETF", "score": 0.9, "raw": "drop"}],
        },
    }


def test_evidence_tools_are_filtered_by_agent_and_compress_news_payload():
    registry = build_evidence_tool_registry(_evidence())

    assert "news.compressed_context" in [tool.name for tool in registry.list("news")]
    assert "scoring.factor_matrix" not in [tool.name for tool in registry.list("news")]

    payload = registry.invoke("news.compressed_context", code="000001")

    assert payload["news_count"] == 2
    assert payload["evaluation"]["coverage_warning"] == "覆盖偏窄"
    assert "content" not in payload["samples"][0]
    assert "content" not in payload["relevance_task"]["candidate_news"][0]


def test_evidence_tools_expose_portfolio_and_scoring_contexts():
    registry = build_evidence_tool_registry(_evidence())

    scoring = registry.invoke("scoring.factor_matrix", code="000001")
    portfolio = registry.invoke("portfolio.context")
    recs = registry.invoke("recommendations.candidates")

    assert scoring["quant_baseline"]["macro_score"] == 15
    assert portfolio["portfolio"]["total_value"] == 10000
    assert recs["candidates"][0]["code"] == "588710"
    assert "raw" not in recs["candidates"][0]


def test_evidence_tools_expose_agent_v3_extensions():
    registry = build_evidence_tool_registry(_evidence())

    kg = registry.invoke("kg.snapshot", code="000001")
    news = registry.invoke("news.agent_evidence", code="000001")
    score = registry.invoke("scoring.agent_evidence", code="000001")
    strategy = registry.invoke("strategy.evidence", code="000001")

    assert kg["fund_exposure"]["themes"] == ["消费"]
    assert "evt-1" in kg["impact_chains"]
    assert news["research_summaries"][0]["what"] == "发生事件"
    assert score["agent_state"]["final_score"] == 70
    assert strategy["action"] == "hold"
