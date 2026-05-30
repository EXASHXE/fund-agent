import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import networkx as nx
import pandas as pd

from legacy.analysis.scoring.types import ScoreComponent
from legacy.output.report import _render_daily_attribution_section, _render_execution_status
from legacy.cli import cmd_analyze
from legacy.services.workflow_context import build_workflow_context


class WorkflowContextTest(unittest.TestCase):
    def test_monday_before_cutoff_uses_non_trade_day_mode(self):
        config = SimpleNamespace(holdings=[])
        with patch("legacy.services.workflow_context.shared_today", lambda: date(2026, 5, 18)), \
             patch("legacy.services.workflow_context.effective_report_date", lambda: date(2026, 5, 15)), \
             patch("legacy.engine.calendar.is_trade_day", lambda d: d == date(2026, 5, 18)):
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
        with patch("legacy.services.workflow_context.shared_today", lambda: date(2026, 5, 22)), \
             patch("legacy.services.workflow_context.effective_report_date", lambda: date(2026, 5, 22)), \
             patch("legacy.engine.calendar.is_trade_day", lambda d: True):
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
        with patch("legacy.services.workflow_context.shared_today", lambda: date(2026, 5, 23)), \
             patch("legacy.services.workflow_context.effective_report_date", lambda: date(2026, 5, 22)), \
             patch("legacy.engine.calendar.is_trade_day", lambda d: True):
            ctx = build_workflow_context(config, {"by_fund": {}, "funds": []}, news_data)

        self.assertEqual(ctx["top_news"][0]["headline"], "口径内消息")
        self.assertTrue(all(item["date"] <= "2026-05-22" for item in ctx["top_news"]))


    def test_use_agents_invokes_langgraph_research_graph(self):
        graph_calls = []
        render_calls = []

        class FakeAnalyzer:
            def __init__(self):
                self.funds = {}

            def load_fund(self, code):
                return {
                    "code": code,
                    "basic": {"name": "测试基金", "fund_type": "stock"},
                    "completeness": "A",
                    "nav": [1.0, 1.02, 1.04],
                    "holdings": pd.DataFrame([{
                        "股票代码": "600519",
                        "股票名称": "贵州茅台",
                        "占净值比例": 6.0,
                        "行业": "食品饮料",
                    }]),
                    "sectors": pd.DataFrame([{"行业名称": "食品饮料", "占净值比例": 30.0}]),
                }

        class FakeResearchGraph:
            def invoke(self, state):
                graph_calls.append(state)
                return {
                    "search_plans": {"000001": {}},
                    "scored_news": {"000001": []},
                    "extracted_events": {"000001": []},
                    "market_regime": "trending",
                    "quant_scores": {"000001": ScoreComponent(
                        score=81.0,
                        detail={"sharpe": 1.2},
                        weights={"sharpe": 0.4},
                        confidence=0.82,
                    )},
                    "fundamental_scores": {"000001": ScoreComponent(
                        score=73.0,
                        detail={"industry": "positive"},
                        weights={},
                        confidence=0.75,
                    )},
                    "event_scores": {"000001": ScoreComponent(
                        score=66.0,
                        detail={"event_count": 1},
                        weights={},
                        confidence=0.61,
                    )},
                    "position_scores": {"000001": ScoreComponent(
                        score=69.0,
                        detail={"concentration": "moderate"},
                        weights={},
                        confidence=0.7,
                    )},
                    "timing_scores": {"000001": ScoreComponent(
                        score=64.0,
                        detail={"watch_signal": "wait"},
                        weights={},
                        confidence=0.68,
                    )},
                    "strategies": {"000001": SimpleNamespace(
                        action=SimpleNamespace(value="hold"),
                        confidence=0.7,
                        risk_level="medium",
                        reasons=["测试策略"],
                        trigger_events=[],
                        position_suggestion="hold",
                        time_horizon="medium",
                    )},
                    "risk_assessments": {"000001": {}},
                    "final_scores": {"000001": 70.0},
                    "portfolio_strategy": {"fund_count": 1},
                }

        class FakeNewsPipeline:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, codes, graph):
                return {code: {"scored_news": [], "events": []} for code in codes}

        class FakeStrategyEngine:
            def analyze_fund(self, code, fund_data, graph, events):
                return SimpleNamespace(
                    action=SimpleNamespace(value="hold"),
                    confidence=0.7,
                    risk_level="medium",
                    reasons=["测试策略"],
                    trigger_events=[],
                    position_suggestion="hold",
                    time_horizon="medium",
                )

        score = {
            "fund_code": "000001",
            "fund_name": "测试基金",
            "data_completeness": "A",
            "composite_score": 70,
            "score_level": "yellow",
            "score_level_emoji": "🟡",
            "macro_score": 14,
            "macro_basis": "",
            "meso_score": 20,
            "meso_basis": "",
            "micro_score": 36,
            "micro_basis": "",
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
            fallback_keywords=False,
            agent_decisions=None,
            snapshot_after=False,
        )

        kg = nx.DiGraph()
        kg.add_node("fund:000001")

        with patch("src.infra.config.loader.load_portfolio_config", lambda path: config), \
             patch("src.infra.config.loader.import_to_database", lambda config: None), \
             patch("src.infra.persistence.storage.FundStorage", lambda: store), \
             patch("legacy.analysis.loader.FundDataLoader", FakeAnalyzer), \
             patch("legacy.analysis.correlation.compute_correlations", lambda funds: pd.DataFrame()), \
             patch("legacy.workflows.workflow._build_unified_graph", lambda funds, codes: kg), \
             patch("legacy.agents.graphs.supervisor.build_research_graph", lambda: FakeResearchGraph()), \
             patch("legacy.news.news_pipeline.NewsPipeline", FakeNewsPipeline), \
             patch("legacy.news.finnhub_client.FinnhubNewsClient", lambda: None), \
             patch("legacy.news.tavily_client.TavilySearchClient", lambda: None), \
             patch("legacy.strategy.engine.StrategyEngine", FakeStrategyEngine), \
             patch("legacy.workflows.workflow._score_with_new_engine", lambda codes, funds, graph, news_results: ([dict(score)], [])), \
             patch("legacy.workflows.workflow.compute_holdings", lambda store, config, codes, funds: {"by_fund": {}, "funds": [], "total_value": 0}), \
             patch("legacy.workflows.workflow.build_workflow_context", lambda config, holdings_data, news_data=None: {"is_trade_day": True}), \
             patch("legacy.workflows.workflow.render_analysis_report", lambda **kwargs: render_calls.append(kwargs) or SimpleNamespace(evidence_path="/tmp/report.evidence.json")), \
             patch("legacy.workflows.workflow.save_snapshot", lambda *args, **kwargs: None):
            cmd_analyze(args)

        self.assertEqual(len(graph_calls), 1)
        self.assertEqual(sorted(graph_calls[0]["funds_data"]), ["000001"])
        self.assertIs(graph_calls[0]["knowledge_graph"], kg)
        self.assertIn("kg_snapshot", render_calls[0]["workflow_context"])
        self.assertEqual(
            render_calls[0]["scores"][0]["agent_score_context"]["portfolio_strategy"],
            {"fund_count": 1},
        )
        agent_state_evidence = render_calls[0]["scores"][0]["score_evidence"]["agent_state"]
        self.assertEqual(agent_state_evidence["market_regime"], "trending")
        self.assertEqual(agent_state_evidence["quant_score"]["score"], 81.0)
        self.assertEqual(agent_state_evidence["fundamental_score"]["detail"]["industry"], "positive")
        self.assertEqual(agent_state_evidence["final_score"], 70.0)

    def test_use_agents_empty_kg_still_scores_and_renders(self):
        scoring_calls = []
        render_calls = []
        strategy_calls = []

        class FakeLoader:
            def load_fund(self, code):
                return {
                    "basic": {"name": "测试基金", "fund_type": "stock"},
                    "completeness": "A",
                    "nav": [1.0, 1.01, 1.02],
                }

        score = {
            "fund_code": "000001",
            "fund_name": "测试基金",
            "data_completeness": "A",
            "composite_score": 68,
            "score_level": "yellow",
            "score_level_emoji": "🟡",
            "macro_score": 13,
            "macro_basis": "",
            "meso_score": 19,
            "meso_basis": "",
            "micro_score": 36,
            "micro_basis": "",
            "recommendation": "持有",
            "stop_profit_pct": 20,
            "stop_loss_pct": -15,
            "action_logic": "",
        }

        def fake_score(codes, funds, graph, news_results):
            scoring_calls.append((codes, graph, news_results))
            return [dict(score)], []

        def fake_render(**kwargs):
            render_calls.append(kwargs)
            return SimpleNamespace(evidence_path="/tmp/report.evidence.json")

        class FakeStrategyEngine:
            def analyze_fund(self, code, fund_data, graph, events):
                strategy_calls.append((code, graph, events))
                return SimpleNamespace(
                    action=SimpleNamespace(value="wait"),
                    confidence=0.55,
                    risk_level="medium",
                    reasons=["KG 为空，等待数据确认"],
                    trigger_events=["补齐持仓行业后复核"],
                    position_suggestion="wait",
                    time_horizon="short",
                )

        config = SimpleNamespace(holdings=[SimpleNamespace(code="000001")])
        store = SimpleNamespace(get_fund_score_history=lambda code, limit=50: [])
        args = SimpleNamespace(
            config="fund-portfolio.yaml",
            output="/tmp/fund-agent-test-report.md",
            recommend=False,
            stress=False,
            news_keyword_cache=None,
            fallback_keywords=False,
            agent_decisions=None,
            snapshot_after=False,
        )

        with patch("src.infra.config.loader.load_portfolio_config", lambda path: config), \
             patch("src.infra.config.loader.import_to_database", lambda config: None), \
             patch("src.infra.persistence.storage.FundStorage", lambda: store), \
             patch("legacy.analysis.loader.FundDataLoader", FakeLoader), \
             patch("legacy.analysis.correlation.compute_correlations", lambda funds: pd.DataFrame()), \
             patch("legacy.workflows.workflow._build_unified_graph", lambda funds, codes: nx.DiGraph()), \
             patch("legacy.workflows.workflow._score_with_new_engine", fake_score), \
             patch("legacy.strategy.engine.StrategyEngine", lambda: FakeStrategyEngine()), \
             patch("legacy.workflows.workflow.compute_holdings", lambda store, config, codes, funds: {"by_fund": {}, "funds": [], "total_value": 0}), \
             patch("legacy.workflows.workflow.build_workflow_context", lambda config, holdings_data, news_data=None: {"is_trade_day": True}), \
             patch("legacy.workflows.workflow.render_analysis_report", fake_render), \
             patch("legacy.workflows.workflow.save_snapshot", lambda *args, **kwargs: None):
            cmd_analyze(args)

        self.assertEqual(len(scoring_calls), 1)
        self.assertEqual(scoring_calls[0][2], {})
        self.assertEqual(render_calls[0]["scores"][0]["fund_code"], "000001")
        self.assertEqual(len(strategy_calls), 1)
        self.assertEqual(render_calls[0]["scores"][0]["_strategy_advice"]["action"], "wait")


if __name__ == "__main__":
    unittest.main()
