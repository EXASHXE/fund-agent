import unittest

import pandas as pd

from src.output.report import generate_report
from src.output.report import _format_profit_contribution, _render_daily_reasoning


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

    def test_profit_contribution_keeps_gain_positive_when_total_week_loss(self):
        self.assertEqual(_format_profit_contribution(50, -200), "+25.00%")
        self.assertEqual(_format_profit_contribution(-250, -200), "-125.00%")

    def test_daily_reasoning_uses_agent_low_relevance_news_judgment(self):
        text = _render_daily_reasoning(
            workflow_context={
                "top_news": [{
                    "code": "021620",
                    "name": "天弘石油天然气指数C",
                    "headline": "美股纳指高开0.2% 芯片股反弹",
                    "sentiment": 0.8,
                }]
            },
            holdings_data={},
            scores=[],
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

        self.assertIn("相关性低", text)
        self.assertNotIn("利好/支撑", text)

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


if __name__ == "__main__":
    unittest.main()
