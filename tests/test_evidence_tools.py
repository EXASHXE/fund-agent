from src.tools.evidence_tools import build_evidence_tool_registry


def _evidence():
    return {
        "portfolio": {"total_value": 10000},
        "portfolio_evidence": {"risk_matrix": {"warnings": ["集中"]}},
        "workflow_evidence": {"settlement_rows": [{"code": "000001"}]},
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
