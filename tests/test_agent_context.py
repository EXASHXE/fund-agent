import unittest
from datetime import date, timedelta

import pandas as pd

from src.analysis.scorer import FundAnalyzer
from src.news.agent_context import (
    build_news_judgment_context,
    build_recommendation_judgment_context,
)


class AgentContextTest(unittest.TestCase):
    def test_score_fund_returns_agent_review_context_without_api_call(self):
        analyzer = FundAnalyzer()
        start = date(2025, 1, 1)
        nav = pd.DataFrame(
            {
                "单位净值": [1 + i * 0.001 for i in range(260)],
                "日增长率": [0.1 for _ in range(260)],
            },
            index=[start + timedelta(days=i) for i in range(260)],
        )
        analyzer.funds["000001"] = {
            "basic": {"name": "测试混合基金", "fund_type": "混合型", "manager": "张三"},
            "perf": {
                "近1年": {"sharpe_ratio": 1.2, "annual_volatility": 12.0},
                "近3年": {"sharpe_ratio": 1.1, "max_drawdown": 18.0},
            },
            "nav": nav,
            "holdings": pd.DataFrame([{"股票名称": "寒武纪", "占净值比例": "8.2%"}]),
            "sectors": pd.DataFrame([{"行业": "半导体", "占比": "35%"}]),
            "holders": pd.DataFrame(),
            "completeness": "A",
        }

        score = analyzer.score_fund("000001")

        self.assertEqual(score["score_source"], "rules_seed")
        self.assertTrue(score["agent_review_required"])
        self.assertEqual(score["agent_score_context"]["task"], "agent_score_judgment")
        self.assertEqual(score["agent_score_context"]["rule_score_seed"]["composite_score"], 70)

    def test_score_fund_includes_news_context_when_provided_before_scoring(self):
        analyzer = FundAnalyzer()
        start = date(2025, 1, 1)
        nav = pd.DataFrame(
            {
                "单位净值": [1 + i * 0.001 for i in range(260)],
                "日增长率": [0.1 for _ in range(260)],
            },
            index=[start + timedelta(days=i) for i in range(260)],
        )
        analyzer.funds["000001"] = {
            "basic": {"name": "测试混合基金", "fund_type": "混合型", "manager": "张三"},
            "perf": {
                "近1年": {"sharpe_ratio": 1.2, "annual_volatility": 12.0},
                "近3年": {"sharpe_ratio": 1.1, "max_drawdown": 18.0},
            },
            "nav": nav,
            "holdings": pd.DataFrame([{"股票名称": "寒武纪", "占净值比例": "8.2%"}]),
            "sectors": pd.DataFrame([{"行业": "半导体", "占比": "35%"}]),
            "holders": pd.DataFrame(),
            "completeness": "A",
        }

        score = analyzer.score_fund("000001", news_context={
            "fund_code": "000001",
            "sentiment_mean": 0.68,
            "brief": {
                "trend": "bullish",
                "weighted_catalyst_score": 0.24,
                "top_events": [{"event_type": "订单增长", "score": 0.31}],
            },
        })

        fund_context = score["agent_score_context"]["fund_context"]
        self.assertEqual(fund_context["news_context"]["brief"]["trend"], "bullish")
        self.assertEqual(fund_context["news_context"]["sentiment_mean"], 0.68)

    def test_news_context_contains_samples_and_instruction(self):
        context = build_news_judgment_context(
            fund_name="测试基金",
            fund_code="000001",
            news_list=[{"title": "寒武纪业绩预增", "content": "半导体需求改善", "sentiment_score": 0.8}],
            daily_aggregates=[{"date": "2026-05-18", "sentiment_mean": 0.7}],
            nav_summary="近20日上涨",
            holding_context="重仓寒武纪、精测电子",
        )

        self.assertEqual(context["task"], "agent_news_judgment")
        self.assertIn("不要编造", context["instruction"])
        self.assertEqual(context["news_samples"][0]["title"], "寒武纪业绩预增")

    def test_recommendation_context_marks_candidates_as_non_final(self):
        context = build_recommendation_judgment_context(
            recommendations=[{"code": "100001", "name": "科技基金"}],
            holding_profiles=[{"code": "000001", "theme": "半导体"}],
            hot_sectors={"半导体": 1.0},
        )

        self.assertEqual(context["task"], "agent_recommendation_judgment")
        self.assertIn("候选列表是筛选结果", context["instruction"])
        self.assertEqual(context["rule_ranked_candidates"][0]["code"], "100001")


    def test_build_news_relevance_task_includes_holdings_and_news(self):
        from src.news.agent_context import build_news_relevance_task
        from src.news.schemas import EntityProfile

        entity = EntityProfile(
            fund_code="008253",
            fund_name="华宝致远混合A",
            stock_codes=["NVDA", "MU"],
            stock_names=["英伟达", "美光科技"],
            holdings=[
                {"stock_code": "NVDA", "stock_name": "英伟达", "weight": 0.0779},
                {"stock_code": "MU", "stock_name": "美光科技", "weight": 0.0453},
            ],
            sector_keywords=["半导体"],
            theme_keywords=["芯片"],
        )

        news_with_catalyst = [
            {
                "title": "英伟达Q1财报超预期",
                "content": "英伟达发布强劲财报",
                "date": "2026-05-22",
                "source": "财联社",
                "matched_terms": ["英伟达"],
                "catalyst": {"relevance": 0.85, "weighted_score": 0.42},
            },
            {
                "title": "雷军回应重新发布YU7标准版",
                "content": "少了一款竞争产品特别不利",
                "date": "2026-05-22",
                "source": "财联社",
                "matched_terms": ["AI"],
                "catalyst": {"relevance": 0.20, "weighted_score": 0.02},
            },
        ]

        task = build_news_relevance_task("华宝致远混合A", "008253", entity, news_with_catalyst)

        self.assertEqual(task["task"], "agent_news_relevance")
        self.assertEqual(len(task["holdings"]), 2)
        self.assertEqual(task["holdings"][0]["name"], "英伟达")
        self.assertEqual(len(task["candidate_news"]), 2)
        self.assertEqual(task["candidate_news"][0]["rule_relevance"], 0.85)
        self.assertEqual(task["candidate_news"][1]["rule_relevance"], 0.20)
        self.assertIn("实质性投资关联", task["instruction"])


if __name__ == "__main__":
    unittest.main()
