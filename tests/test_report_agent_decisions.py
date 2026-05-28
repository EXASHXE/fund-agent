from datetime import date
import json
import tempfile
import unittest

import pandas as pd

from src.core.contracts import (
    build_report_evidence as _build_report_evidence,
    load_agent_decisions as _load_agent_decisions,
)
from src.output.report import _format_profit_contribution, generate_report
from src.output.templates import qdii_hint
from src.output.validator import post_process_report, validate_final_report


def _score(code="000001", name="测试基金"):
    return {
        "fund_code": code,
        "fund_name": name,
        "data_completeness": "A",
        "composite_score": 76,
        "score_confidence": 0.88,
        "score_level": "green",
        "score_level_emoji": "🟢",
        "macro_score": 15,
        "macro_basis": "",
        "meso_score": 22,
        "meso_basis": "",
        "micro_score": 39,
        "micro_basis": "",
        "recommendation": "买入",
        "action_logic": "旧规则动作不得成为最终结论",
        "stop_profit_pct": 20,
        "stop_loss_pct": -15,
        "agent_review_required": True,
        "trend_matrix": {
            "short_term": {"direction": "up", "score": 0.72, "confidence": 0.8},
            "mid_term": {"direction": "flat", "score": 0.58, "confidence": 0.7},
            "drivers": ["新闻催化偏正"],
        },
        "operation_advice": {
            "action": "buy",
            "target_weight": 0.18,
            "adjust_amount": 1000,
            "confidence": 0.75,
            "triggers": ["规则触发条件不得作为最终结论"],
        },
    }


def _valid_decisions():
    return {
        "schema_version": "agent_decisions.v2",
        "evidence_report_date": "2026-05-22",
        "portfolio": {"tldr": "维持均衡", "stance": "neutral", "daily_analysis": "测试当日归因"},
        "fund_scores": {
            "000001": {
                "final_scores": {"macro": 16, "meso": 22, "micro": 39, "total": 77},
                "agent_adjustments": {"macro": 1, "meso": 0, "micro": 0},
                "final_action": "hold",
                "target_weight_pct": 18.0,
                "adjust_amount": 0,
                "rationale": ["测试依据"],
                "triggers": ["测试触发"],
            }
        },
        "recommendations": [],
    }


class ReportAgentDecisionTest(unittest.TestCase):
    def test_empty_agent_recommendations_do_not_fallback_to_rule_candidates(self):
        report = generate_report(
            analyzer=None,
            scores=[],
            correlations=pd.DataFrame(),
            stress_tests=[],
            recommendations=[{"code": "588710", "name": "半导体ETF", "theme": "半导体", "score": 0.84}],
            agent_decisions={"recommendations": []},
        )
        self.assertNotIn("588710", report)
        self.assertIn("本次 Agent 未给出最终推荐", report)

    def test_profit_contribution_keeps_gain_positive_when_total_abs_denom(self):
        self.assertEqual(_format_profit_contribution(50, 250), "+20.00%")
        self.assertEqual(_format_profit_contribution(-250, 250), "-100.00%")
        self.assertEqual(_format_profit_contribution(0, 250), "+0.00%")

    def test_evidence_report_has_no_agent_placeholders_or_rule_operation_sections(self):
        report = generate_report(
            analyzer=None,
            scores=[_score()],
            correlations=pd.DataFrame(),
            stress_tests=[],
            holdings_data={"total_value": 10000, "funds": []},
            news_data=[],
            recommendations=[],
        )
        self.assertIn("证据稿", report)
        self.assertIn("待 Agent 最终评定", report)
        self.assertNotIn("<!-- AGENT:", report)
        self.assertNotIn("AGENT_FILL", report)
        self.assertNotIn("趋势预测与操作矩阵", report)
        self.assertNotIn("操作触发条件", report)
        self.assertNotIn("建议占比", report)
        self.assertNotIn("调整金额", report)
        for title in [
            "## 四、单基金深度诊断",
            "## 五、组合研判与执行方案",
            "## 六、组合风险、相关性与压力测试",
            "## 七、推荐候选与观察池",
        ]:
            self.assertIn(title, report)

    def test_news_low_relevance_renders_agent_limitation(self):
        report = generate_report(
            analyzer=None,
            scores=[_score("021620", "天弘石油天然气指数C")],
            correlations=pd.DataFrame(),
            stress_tests=[],
            news_data=[{
                "fund_code": "021620",
                "fund_name": "天弘石油天然气指数C",
                "news_count": 1,
                "sentiment_mean": 0.8,
                "daily_aggregates": [],
                "news_list": [],
                "news_evaluation": {
                    "quality_score": 0.2,
                    "holding_coverage_pct": 0.25,
                    "coverage_warning": "覆盖偏窄",
                },
                "status": "ok",
            }],
            agent_decisions={
                "news": {
                    "021620": {
                        "summary": "本次新闻样本与油气指数直接相关性不足",
                        "impact": "neutral",
                        "relevance": "low",
                        "confidence": 0.2,
                    }
                }
            },
        )
        self.assertIn("本次新闻样本与油气指数直接相关性不足", report)
        self.assertIn("覆盖偏窄", report)
        self.assertIn("25.00%", report)

    def test_report_renders_final_scores_and_actions_only_from_agent_decisions(self):
        report = generate_report(
            analyzer=None,
            scores=[_score()],
            correlations=pd.DataFrame(),
            stress_tests=[],
            holdings_data={
                "total_value": 10000,
                "funds": [{"code": "000001", "name": "测试基金", "value": 10000}],
            },
            agent_decisions={
                "portfolio": {"tldr": "维持均衡配置", "stance": "neutral"},
                "fund_scores": {
                    "000001": {
                        "final_scores": {"macro": 16, "meso": 21, "micro": 40, "total": 77},
                        "agent_adjustments": {"macro": 1, "meso": -1, "micro": 1},
                        "final_action": "hold",
                        "target_weight_pct": 18.0,
                        "adjust_amount": -500.0,
                        "rationale": ["估值约束抵消短期催化"],
                        "triggers": ["回撤扩大后复核"],
                    }
                },
                "recommendations": [],
            },
        )
        self.assertIn("Agent 最终研判", report)
        self.assertIn("77/100", report)
        self.assertIn("<tr><td>综合</td><td>76</td><td>+1</td><td>77</td>", report)
        self.assertIn("hold", report)
        self.assertIn("18.00%", report)
        self.assertIn("-500.00", report)
        self.assertNotIn("规则初稿；尚未提供", report)

    def test_fund_diagnostics_use_balanced_details_blocks(self):
        report = generate_report(
            analyzer=None,
            scores=[_score()],
            correlations=pd.DataFrame(),
            stress_tests=[],
        )
        self.assertNotIn("<details markdown=\"1\">", report)
        self.assertEqual(report.count("<details>"), report.count("</details>"))
        self.assertIn("<summary>测试基金（000001）", report)
        self.assertIn("<table>", report)

    def test_agent_decisions_contract_rejects_score_that_cannot_reconcile(self):
        payload = {
            "schema_version": "agent_decisions.v2",
            "evidence_report_date": "2026-05-22",
            "portfolio": {"tldr": "测试", "stance": "neutral", "daily_analysis": "测试"},
            "fund_scores": {
                "000001": {
                    "final_scores": {"macro": 16, "meso": 21, "micro": 40, "total": 99},
                    "agent_adjustments": {"macro": 1, "meso": -1, "micro": 1},
                    "final_action": "hold",
                    "target_weight_pct": 18.0,
                    "adjust_amount": 0,
                    "rationale": ["测试依据"],
                    "triggers": ["测试触发"],
                }
            },
            "recommendations": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "综合分无法与分项合计对账"):
                _load_agent_decisions(handle.name, date(2026, 5, 22), scores=[_score()])

    def test_evidence_contains_workflow_and_candidate_inputs_for_agent(self):
        evidence = _build_report_evidence(
            date(2026, 5, 22),
            [_score()],
            {"by_fund": {}},
            [],
            pd.DataFrame(),
            [],
            {},
            recommendations=[{"code": "588710", "name": "半导体ETF"}],
            recommendation_status="ok",
            workflow_context={"settlement_rows": [{"code": "000001"}], "dca_rows": []},
        )
        self.assertEqual(evidence["recommendation_evidence"]["candidates"][0]["code"], "588710")
        self.assertEqual(evidence["workflow_evidence"]["settlement_rows"][0]["code"], "000001")

    def test_agent_recommendation_must_have_candidate_evidence(self):
        payload = _valid_decisions()
        payload["recommendations"] = [{"code": "588710", "name": "半导体ETF"}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "缺少本次候选证据"):
                _load_agent_decisions(
                    handle.name,
                    date(2026, 5, 22),
                    scores=[_score()],
                    recommendation_candidates=[],
                )

    def test_agent_target_weights_cannot_exceed_full_portfolio(self):
        payload = _valid_decisions()
        payload["fund_scores"]["000001"]["target_weight_pct"] = 60.0
        payload["fund_scores"]["000002"] = {
            **payload["fund_scores"]["000001"],
            "target_weight_pct": 50.0,
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "目标配置合计超过 100%"):
                _load_agent_decisions(
                    handle.name,
                    date(2026, 5, 22),
                    scores=[_score(), _score("000002", "第二基金")],
                )

    def test_final_validator_rejects_evidence_draft_and_accepts_agent_report(self):
        evidence_report = generate_report(None, [_score()], pd.DataFrame(), [])
        with self.assertRaisesRegex(ValueError, "禁用的旧输出内容"):
            validate_final_report(evidence_report, "2026-05-22", 0)

        final_report = generate_report(
            None, [_score()], pd.DataFrame(), [], agent_decisions=_valid_decisions()
        )
        validate_final_report(final_report, "2026-05-22", 0)

    def test_domestic_oil_index_is_not_marked_as_qdii_nav_lag(self):
        self.assertEqual(qdii_hint("天弘石油天然气指数C", "index"), "")
        self.assertNotIn("T-1估算净值", qdii_hint("海外科技(QDII)", "qdii"))

    def test_post_process_report_with_nav_lag_hint(self):
        raw_markdown = """
### 华宝纳斯达克精选股票(QDII)A（017436） ⚠️*(海外净值披露可能滞后)*

| 指标 | 设定值 |
|------|------|
| **止盈线** | +20.00% |
| **止损线** | -15.00% |

## 风险提示
- 原始风险提示
"""
        scores = [{"fund_code": "017436", "fund_name": "华宝纳斯达克精选股票(QDII)A", "annual_volatility": 25.0}]
        processed = post_process_report(raw_markdown, scores)
        self.assertIn("| **止盈线** | +50.00%", processed)
        self.assertIn("| **止损线** | -37.50%", processed)
        self.assertNotIn("- 原始风险提示", processed)

    def test_post_process_report_calibrates_html_details_stop_bounds(self):
        raw_markdown = """
<details>
<summary>华宝纳斯达克精选股票(QDII)A（017436） ⚠️*(海外净值披露可能滞后)*</summary>
<div>
<table>
<tbody>
<tr><td>止盈线</td><td>+20.00%</td><td>待 Agent 设定</td></tr>
<tr><td>止损线</td><td>-15.00%</td><td>待 Agent 设定</td></tr>
</tbody>
</table>
</div>
</details>

## 风险提示
- 原始风险提示
"""
        scores = [{"fund_code": "017436", "fund_name": "华宝纳斯达克精选股票(QDII)A", "annual_volatility": 25.0}]
        processed = post_process_report(raw_markdown, scores)
        self.assertIn("<tr><td>止盈线</td><td>+50.00%</td>", processed)
        self.assertIn("<tr><td>止损线</td><td>-37.50%</td>", processed)


if __name__ == "__main__":
    unittest.main()
