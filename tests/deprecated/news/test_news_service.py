from legacy.services.news_service import build_nav_summary, news_context_by_code, planned_news_keywords


def test_planned_news_keywords_splits_compound_terms_and_preserves_order():
    plan = {
        "funds": {
            "000001": {
                "keywords": ["英伟达 NVDA 财报", "HBM"],
                "expanded_keywords": ["英伟达", "台积电"],
            }
        }
    }

    assert planned_news_keywords(plan, "000001") == ["英伟达", "NVDA", "财报", "HBM", "台积电"]


def test_news_context_by_code_keeps_top_catalysts_compact():
    context = news_context_by_code([
        {
            "fund_code": "000001",
            "fund_name": "测试基金",
            "status": "ok",
            "news_count": 2,
            "sentiment_mean": 0.7,
            "daily_aggregates": [{"d": 1}, {"d": 2}],
            "brief": {"summary": "brief"},
            "news_evaluation": {"quality_score": 0.8},
            "catalyst_news": [
                {"title": "low", "date": "2026-05-22", "catalyst": {"weighted_score": 0.1}},
                {"title": "high", "date": "2026-05-22", "catalyst": {"weighted_score": -0.9}},
            ],
        }
    ])

    assert context["000001"]["top_catalysts"][0]["title"] == "high"
    assert context["000001"]["brief"] == {"summary": "brief"}


def test_build_nav_summary_handles_empty_and_recent_returns():
    assert build_nav_summary([]) == "无净值收益率数据"
    assert "近20个可用交易日平均日增长率 +1.00%" in build_nav_summary([
        ("2026-05-21", 0.5),
        ("2026-05-22", 1.5),
    ])
