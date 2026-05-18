"""Agent 判断上下文构造器。

本项目的 fund-analyst 是给 AI agent 使用的 skill，模型推理应由接入
skill 的 agent 直接完成，而不是由 Python 代码再通过 API 调用另一个模型。
该模块只负责把脚本采集到的证据整理成适合 agent 阅读和二次判断的结构。
"""
from typing import Dict, List


def build_news_judgment_context(
    fund_name: str,
    fund_code: str,
    news_list: List[Dict],
    daily_aggregates: List[Dict],
    nav_summary: str,
    holding_context: str = "",
) -> Dict:
    """整理新闻证据，供 agent 自主判断事件影响和情绪。"""
    compact_news = [
        {
            "date": n.get("date", ""),
            "title": n.get("title", "")[:140],
            "content": n.get("content", "")[:260],
            "rule_sentiment": n.get("sentiment_score"),
            "source": n.get("source", ""),
        }
        for n in (news_list or [])[:12]
    ]
    return {
        "task": "agent_news_judgment",
        "instruction": (
            "请基于基金真实重仓、新闻标题/摘要、日度情绪和净值摘要，自主判断"
            "新闻事件对基金短期和中期的影响；不要编造未给出的新闻事实。"
        ),
        "fund_code": fund_code,
        "fund_name": fund_name,
        "holding_context": holding_context,
        "nav_summary": nav_summary,
        "daily_aggregates": daily_aggregates or [],
        "news_samples": compact_news,
        "expected_agent_output": {
            "summary": "一句话事件总结",
            "sentiment": "positive/neutral/negative/mixed",
            "short_term_view": "1-2周影响",
            "mid_term_view": "1-3月影响",
            "risk_factors": ["风险1", "风险2"],
            "confidence": "high/medium/low",
        },
    }


def build_score_judgment_context(fund_context: Dict, rule_score: Dict) -> Dict:
    """整理评分证据，供 agent 自主校准规则评分。"""
    return {
        "task": "agent_score_judgment",
        "instruction": (
            "规则分只是初稿。请结合基金基础资料、净值/绩效、持仓行业、新闻、"
            "大盘环境和用户持仓成本，自主给出最终评分与操作建议。"
        ),
        "fund_context": fund_context,
        "rule_score_seed": rule_score,
        "expected_agent_output": {
            "composite_score": "0-100",
            "macro_score": "0-20",
            "meso_score": "0-30 or null",
            "micro_score": "0-50",
            "recommendation": "买入/持有/观察/减仓/止损等",
            "action_logic": "结合仓位、成本、定投和风险的具体动作",
            "confidence": "high/medium/low",
        },
    }


def build_recommendation_judgment_context(
    recommendations: List[Dict],
    holding_profiles: List[Dict],
    hot_sectors: Dict[str, float],
) -> Dict:
    """整理推荐候选，供 agent 去同质化重排和取舍。"""
    return {
        "task": "agent_recommendation_judgment",
        "instruction": (
            "候选列表是筛选结果，不是最终推荐。请优先控制与现有持仓和候选之间"
            "的同质化，避免多个半导体/新能源/电池等同一成长制造链条标的扎堆。"
        ),
        "current_holdings": holding_profiles,
        "hot_sectors": hot_sectors,
        "rule_ranked_candidates": recommendations,
        "expected_agent_output": {
            "final_recommendations": [
                {
                    "code": "基金代码",
                    "reason": "机会、互补性、风险和买入方式",
                    "role_in_portfolio": "防守/海外/红利/固收/商品/成长补充等",
                    "confidence": "high/medium/low",
                }
            ]
        },
    }
