import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from src.output.report import _render_daily_attribution_section, _render_execution_status
from src.cli import cmd_analyze
from src.services.workflow_context import build_workflow_context


class WorkflowContextTest(unittest.TestCase):
    def test_monday_before_cutoff_uses_non_trade_day_mode(self):
        config = SimpleNamespace(holdings=[])
        with patch("src.services.workflow_context.shared_today", lambda: date(2026, 5, 18)), \
             patch("src.services.workflow_context.effective_report_date", lambda: date(2026, 5, 15)), \
             patch("src.engine.calendar.is_trade_day", lambda d: d == date(2026, 5, 18)):
            ctx = build_workflow_context(config, {"by_fund": {}, "funds": []})

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
            "settlement_rows": [],
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

        report = "\n".join(_render_daily_attribution_section(ctx, holdings, {}))

        self.assertIn("归因分析", report)
        self.assertNotIn("周期多维收益贡献", report)

    def test_non_trade_day_report_renders_weekly_review_not_daily_review(self):
        ctx = {
            "run_date": "2026-05-23",
            "report_date": "2026-05-22",
            "mode_reason": "使用上一口径日数据",
            "is_trade_day": False,
            "dca_rows": [],
            "settlement_rows": [],
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

        report = "\n".join(_render_daily_attribution_section(ctx, holdings, {}))

        self.assertIn("周期多维收益贡献", report)
        self.assertNotIn("归因分析", report)

    def test_settlement_table_covers_all_funds_after_dca_table(self):
        holding_a = SimpleNamespace(code="000001", name="国内基金", type="domestic", dca=None)
        holding_b = SimpleNamespace(code="017436", name="海外基金(QDII)", type="qdii", dca=None)
        config = SimpleNamespace(holdings=[holding_a, holding_b])
        holdings = {
            "funds": [
                {"code": "000001", "name": "国内基金"},
                {"code": "017436", "name": "海外基金(QDII)"},
            ],
            "by_fund": {
                "000001": {"settle_delay": 1, "nav_date": "2026-05-22", "current_nav": 1, "total_shares": 10, "engine_events": []},
                "017436": {"settle_delay": 2, "nav_date": "2026-05-21", "current_nav": 2, "total_shares": 20, "engine_events": []},
            },
        }
        with patch("src.services.workflow_context.shared_today", lambda: date(2026, 5, 22)), \
             patch("src.services.workflow_context.effective_report_date", lambda: date(2026, 5, 22)), \
             patch("src.engine.calendar.is_trade_day", lambda d: True):
            ctx = build_workflow_context(config, holdings)

        self.assertEqual(len(ctx["settlement_rows"]), 2)
        rendered = _render_execution_status(ctx)
        self.assertIn("申购与净值结算状态", rendered)
        self.assertNotIn("QDII 结算状态", rendered)

    def test_workflow_excludes_news_after_report_date_from_daily_clues(self):
        config = SimpleNamespace(holdings=[])
        news_data = [{
            "fund_code": "000001",
            "fund_name": "测试基金",
            "sentiment_mean": 0.7,
            "news_list": [
                {"title": "盘后消息", "date": "2026-05-23"},
                {"title": "口径内消息", "date": "2026-05-22"},
            ],
        }]
        with patch("src.services.workflow_context.shared_today", lambda: date(2026, 5, 23)), \
             patch("src.services.workflow_context.effective_report_date", lambda: date(2026, 5, 22)), \
             patch("src.engine.calendar.is_trade_day", lambda d: True):
            ctx = build_workflow_context(config, {"by_fund": {}, "funds": []}, news_data)

        self.assertEqual(ctx["top_news"][0]["headline"], "口径内消息")
        self.assertTrue(all(item["date"] <= "2026-05-22" for item in ctx["top_news"]))

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

        def fake_news(analyzer, config, agent_news_plan=None, days=7, report_date=None, max_workers=None):
            calls.append("news")
            return [{"fund_code": "000001", "sentiment_mean": 0.6, "brief": {"trend": "bullish"}}]

        with patch("src.config.loader.load_portfolio_config", lambda path: config), \
             patch("src.config.loader.import_to_database", lambda config: None), \
             patch("src.db.storage.FundStorage", lambda: store), \
             patch("src.analysis.scorer.FundAnalyzer", FakeAnalyzer), \
             patch("src.analysis.correlation.compute_correlations", lambda funds: pd.DataFrame()), \
             patch("src.core.workflow.compute_holdings", lambda store, config, codes, analyzer: {"by_fund": {}, "funds": [], "total_value": 0}), \
             patch("src.core.workflow.build_workflow_context", lambda config, holdings_data, news_data=None: {"is_trade_day": True}), \
             patch("src.news.keyword_cache.load_valid_keyword_cache", lambda path, codes, today=None: {"funds": {"000001": {"keywords": ["测试"]}}}), \
             patch("src.news.keyword_cache.default_keyword_cache_path", lambda: "/tmp/cache.json"), \
             patch("src.news.pipeline.run_news_pipeline", fake_news), \
             patch("src.output.report.generate_report", lambda *args, **kwargs: "report"), \
             patch("src.output.validator.post_process_report", lambda report, scores: report), \
             patch("src.core.workflow.save_snapshot", lambda *args, **kwargs: None):
            cmd_analyze(args)

        self.assertEqual(calls[:2], ["news", "score"])

    def test_fallback_keywords_option(self):
        class FakeAnalyzer:
            def __init__(self):
                self.funds = {"000001": {"basic": {"name": "测试基金"}, "completeness": "A"}}

            def load_fund(self, code):
                pass

            def score_fund(self, code, news_context=None):
                return {
                    "fund_code": code,
                    "fund_name": "测试基金",
                    "data_completeness": "A",
                    "composite_score": 70,
                    "score_level": "yellow",
                    "score_level_emoji": "🟡",
                    "macro_score": 14, "macro_basis": "",
                    "meso_score": 20, "meso_basis": "",
                    "micro_score": 36, "micro_basis": "",
                    "recommendation": "持有", "action_logic": "",
                    "stop_profit_pct": 20, "stop_loss_pct": -15,
                }

        config = SimpleNamespace(holdings=[SimpleNamespace(code="000001")])
        store = SimpleNamespace(get_fund_score_history=lambda code, limit=50: [])
        args = SimpleNamespace(
            config="fund-portfolio.yaml",
            output="/tmp/fund-agent-test-report.md",
            recommend=False,
            stress=False,
            news_keyword_cache="/tmp/non_existent_cache.json",
            fallback_keywords=True,
            snapshot_after=False,
        )

        plan_passed_to_news = []

        def fake_news(analyzer, config, agent_news_plan=None, days=7, report_date=None, max_workers=None):
            plan_passed_to_news.append(agent_news_plan)
            return [{"fund_code": "000001", "sentiment_mean": 0.6, "brief": {"trend": "bullish"}}]

        with patch("src.config.loader.load_portfolio_config", lambda path: config), \
             patch("src.config.loader.import_to_database", lambda config: None), \
             patch("src.db.storage.FundStorage", lambda: store), \
             patch("src.analysis.scorer.FundAnalyzer", FakeAnalyzer), \
             patch("src.analysis.correlation.compute_correlations", lambda funds: pd.DataFrame()), \
             patch("src.core.workflow.compute_holdings", lambda store, config, codes, analyzer: {"by_fund": {}, "funds": [], "total_value": 0}), \
             patch("src.core.workflow.build_workflow_context", lambda config, holdings_data, news_data=None: {"is_trade_day": True}), \
             patch("src.news.keyword_cache.load_valid_keyword_cache", lambda path, codes, today=None: None), \
             patch("src.news.news_fetcher.extract_holding_keywords", lambda code, limit: ([], ["重仓股A"])), \
             patch("src.news.news_fetcher._fallback_fund_keywords", lambda name, fund_type: ["兜底词A"]), \
             patch("src.news.pipeline.run_news_pipeline", fake_news), \
             patch("src.output.report.generate_report", lambda *args, **kwargs: "report"), \
             patch("src.output.validator.post_process_report", lambda report, scores: report), \
             patch("src.core.workflow.save_snapshot", lambda *args, **kwargs: None), \
             patch("builtins.open", unittest.mock.mock_open()):
            cmd_analyze(args)

        self.assertEqual(len(plan_passed_to_news), 1)
        self.assertIn("重仓股A", plan_passed_to_news[0]["funds"]["000001"]["keywords"])
        self.assertIn("兜底词A", plan_passed_to_news[0]["funds"]["000001"]["keywords"])


if __name__ == "__main__":
    unittest.main()
