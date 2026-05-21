import unittest

import pandas as pd

from src.output.report import generate_report
from src.output.report import _format_profit_contribution


class ReportAgentDecisionTest(unittest.TestCase):
    def test_empty_agent_recommendations_do_not_fallback_to_rule_candidates(self):
        report = generate_report(
            analyzer=None,
            scores=[],
            correlations=pd.DataFrame(),
            stress_tests=[],
            recommendations=[{
                "code": "588710",
                "name": "科创半导体设备ETF华泰柏瑞",
                "theme": "半导体",
                "score": 0.84,
            }],
            agent_decisions={"recommendations": []},
        )

        self.assertNotIn("588710", report)
        self.assertIn("本次 agent 未给出最终推荐", report)

    def test_profit_contribution_keeps_gain_positive_when_total_abs_denom(self):
        # 分母 = 绝对值之和，贡献率在 [-100%, +100%] 区间
        self.assertEqual(_format_profit_contribution(50, 250), "+20.00%")
        self.assertEqual(_format_profit_contribution(-250, 250), "-100.00%")
        self.assertEqual(_format_profit_contribution(0, 250), "+0.00%")

    def test_daily_reasoning_slot_present_in_report(self):
        """Verify the report contains Agent analysis markers."""
        report = generate_report(
            analyzer=None,
            scores=[{
                "fund_code": "021620",
                "fund_name": "天弘石油天然气指数C",
                "data_completeness": "B",
                "composite_score": 67,
                "score_level": "yellow",
                "score_level_emoji": "🟡",
                "macro_score": 13, "macro_basis": "",
                "meso_score": 15, "meso_basis": "",
                "micro_score": 39, "micro_basis": "",
                "recommendation": "持有", "action_logic": "",
                "stop_profit_pct": 10, "stop_loss_pct": -10,
            }],
            correlations=pd.DataFrame(),
            stress_tests=[],
            news_data=[{
                "fund_code": "021620",
                "fund_name": "天弘石油天然气指数C",
                "news_count": 1, "sentiment_mean": 0.5,
                "daily_aggregates": [],
                "news_list": [], "status": "ok",
            }],
            recommendations=[],
            agent_decisions={},
        )
        self.assertIn("AGENT: 诊断分析", report)
        self.assertIn("AGENT: 新闻穿透分析", report)

    def test_news_section_low_relevance_does_not_render_rule_positive_interpretation(self):
        report = generate_report(
            analyzer=None,
            scores=[{
                "fund_code": "021620",
                "fund_name": "天弘石油天然气指数C",
                "data_completeness": "B",
                "composite_score": 67,
                "score_level": "yellow",
                "score_level_emoji": "🟡",
                "macro_score": 13,
                "macro_basis": "",
                "meso_score": 15,
                "meso_basis": "",
                "micro_score": 39,
                "micro_basis": "",
                "recommendation": "持有",
                "action_logic": "",
                "stop_profit_pct": 10,
                "stop_loss_pct": -10,
            }],
            correlations=pd.DataFrame(),
            stress_tests=[],
            news_data=[{
                "fund_code": "021620",
                "fund_name": "天弘石油天然气指数C",
                "news_count": 1,
                "sentiment_mean": 0.8,
                "daily_aggregates": [{"positive_rate": 1, "negative_rate": 0, "top_keywords": []}],
                "agent_news_context": {"task": "agent_news_judgment"},
                "news_list": [],
                "status": "ok",
            }],
            recommendations=[],
            agent_decisions={
                "news": {
                    "021620": {
                        "summary": "本次新闻样本对油气基金直接相关性不足",
                        "impact": "neutral",
                        "relevance": "low",
                    }
                }
            },
        )

        self.assertIn("不使用规则情绪解读", report)
        self.assertNotIn("近期相关新闻偏正面", report)

    def test_report_renders_trend_and_operation_matrix_when_available(self):
        report = generate_report(
            analyzer=None,
            scores=[{
                "fund_code": "000001",
                "fund_name": "测试基金",
                "data_completeness": "A",
                "composite_score": 76,
                "score_level": "green",
                "score_level_emoji": "🟢",
                "macro_score": 15,
                "macro_basis": "",
                "meso_score": 22,
                "meso_basis": "",
                "micro_score": 39,
                "micro_basis": "",
                "recommendation": "买入",
                "action_logic": "",
                "stop_profit_pct": 20,
                "stop_loss_pct": -15,
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
                },
            }],
            correlations=pd.DataFrame(),
            stress_tests=[],
            holdings_data={"total_value": 10000, "funds": []},
        )

        self.assertIn("趋势预测与操作矩阵", report)
        self.assertIn("测试基金", report)
        self.assertIn("buy", report)
        self.assertIn("18.00%", report)


if __name__ == "__main__":
    unittest.main()
