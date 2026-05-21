import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from src.cli import _build_workflow_context, cmd_analyze
from src.output.report import _render_workflow_focus


class WorkflowContextTest(unittest.TestCase):
    def test_monday_before_cutoff_uses_non_trade_day_mode(self):
        config = SimpleNamespace(holdings=[])
        with patch("src.cli._shared_today", lambda: date(2026, 5, 18)), \
             patch("src.cli.effective_report_date", lambda: date(2026, 5, 15)), \
             patch("src.engine.calendar.is_trade_day", lambda d: d == date(2026, 5, 18)):
            ctx = _build_workflow_context(config, {"by_fund": {}, "funds": []})

        self.assertTrue(ctx["run_is_trade_day"])
        self.assertFalse(ctx["is_trade_day"])
        self.assertEqual(ctx["mode"], "prior_settlement")

    def test_trade_day_report_renders_daily_review_not_weekly_review(self):
        ctx = {
            "run_date": "2026-05-22",
            "report_date": "2026-05-22",
            "mode_reason": "当前交易日数据已过分界点",
            "is_trade_day": True,
            "dca_rows": [],
            "qdii_rows": [],
            "top_news": [{"name": "测试基金", "headline": "半导体订单增长", "sentiment": 0.7}],
        }
        holdings = {
            "total_value": 1000,
            "funds": [{
                "code": "000001",
                "name": "测试基金",
                "value": 1000,
                "day_profit": 12.3,
                "day_return_pct": 1.23,
            }],
        }

        report = _render_workflow_focus(ctx, holdings, scores=[], news_data=[])

        self.assertIn("当日盈亏与归因", report)
        self.assertIn("半导体订单增长", report)
        self.assertNotIn("本周收益与基金贡献", report)

    def test_non_trade_day_report_renders_weekly_review_not_daily_review(self):
        ctx = {
            "run_date": "2026-05-23",
            "report_date": "2026-05-22",
            "mode_reason": "使用上一口径日数据",
            "is_trade_day": False,
            "dca_rows": [],
            "qdii_rows": [],
            "top_news": [],
        }
        holdings = {
            "total_value": 1000,
            "funds": [{
                "code": "000001",
                "name": "测试基金",
                "value": 1000,
                "week_profit": 45.6,
            }],
        }

        report = _render_workflow_focus(ctx, holdings, scores=[], news_data=[])

        self.assertIn("本周收益与基金贡献", report)
        self.assertNotIn("当日盈亏与归因", report)

    def test_analyze_runs_news_before_scoring_and_passes_context(self):
        calls = []

        class FakeAnalyzer:
            def __init__(self):
                self.funds = {}

            def load_fund(self, code):
                self.funds[code] = {"basic": {"name": "测试基金"}, "completeness": "A"}

            def score_fund(self, code, news_context=None):
                calls.append("score")
                assert "news" in calls
                assert news_context is not None
                assert news_context["fund_code"] == code
                return {
                    "fund_code": code,
                    "fund_name": "测试基金",
                    "data_completeness": "A",
                    "composite_score": 70,
                    "score_level": "yellow",
                    "score_level_emoji": "🟡",
                    "macro_score": 14,
                    "macro_basis": "",
                    "macro_detail": {},
                    "meso_score": 20,
                    "meso_basis": "",
                    "meso_detail": {},
                    "micro_score": 36,
                    "micro_basis": "",
                    "micro_detail": {},
                    "recommendation": "持有",
                    "stop_profit_pct": 20,
                    "stop_loss_pct": -15,
                    "action_logic": "",
                }

        config = SimpleNamespace(holdings=[SimpleNamespace(code="000001")])
        store = SimpleNamespace(get_fund_score_history=lambda code, limit=50: [])
        args = SimpleNamespace(
            config="fund-portfolio.yaml",
            output="/tmp/fund-agent-test-report.md",
            recommend=False,
            stress=False,
            news_keyword_cache=None,
            snapshot_after=False,
        )

        def fake_news(config, analyzer, agent_news_plan=None):
            calls.append("news")
            return [{"fund_code": "000001", "sentiment_mean": 0.6, "brief": {"trend": "bullish"}}]

        with patch("src.config.loader.load_portfolio_config", lambda path: config), \
             patch("src.config.loader.import_to_database", lambda config: None), \
             patch("src.db.storage.FundStorage", lambda: store), \
             patch("src.analysis.scorer.FundAnalyzer", FakeAnalyzer), \
             patch("src.analysis.correlation.compute_correlations", lambda funds: pd.DataFrame()), \
             patch("src.cli._compute_holdings", lambda store, config, codes, analyzer: {"by_fund": {}, "funds": [], "total_value": 0}), \
             patch("src.cli._build_workflow_context", lambda config, holdings_data, news_data=None: {"is_trade_day": True}), \
             patch("src.news.keyword_cache.load_valid_keyword_cache", lambda path, codes, today=None: {"funds": {"000001": {"keywords": ["测试"]}}}), \
             patch("src.news.keyword_cache.default_keyword_cache_path", lambda: "/tmp/cache.json"), \
             patch("src.cli._run_news_analysis", fake_news), \
             patch("src.output.report.generate_report", lambda *args, **kwargs: "report"), \
             patch("src.output.validator.post_process_report", lambda report, scores: report), \
             patch("src.cli._save_snapshot", lambda *args, **kwargs: None):
            cmd_analyze(args)

        self.assertEqual(calls[:2], ["news", "score"])


if __name__ == "__main__":
    unittest.main()
