"""Agent 判断上下文构造器。

本项目的 fund-analyst 是给 AI agent 使用的 skill，模型推理应由接入
skill 的 agent 直接完成，而不是由 Python 代码再通过 API 调用另一个模型。
该模块只负责把脚本采集到的证据整理成适合 agent 阅读和二次判断的结构。
"""
from typing import Dict, List


def build_news_judgment_context(
    fund_name: str,
    fund_code: str,
    news_list: list[Dict],
    daily_aggregates: list[Dict],
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
    recommendations: list[Dict],
    holding_profiles: list[Dict],
    hot_sectors: dict[str, float],
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


def build_news_relevance_task(
    fund_name: str,
    fund_code: str,
    entity_profile,
    news_with_catalyst: list[Dict],
) -> Dict:
    """构造新闻相关性判断任务，供 Agent 在执行 skill 时使用。

    任务将持仓信息与候选新闻打包，Agent 需逐条判断是否有实质性投资关联。
    """
    holdings_payload = [
        {
            "name": h.get("stock_name", ""),
            "code": h.get("stock_code", ""),
            "weight_pct": round(h.get("weight", 0) * 100, 2),
        }
        for h in (getattr(entity_profile, "holdings", []) or [])[:10]
    ]

    candidate_news = []
    for i, n in enumerate(news_with_catalyst[:20]):
        catalyst = n.get("catalyst") or {}
        candidate_news.append({
            "id": i + 1,
            "title": (n.get("title") or "")[:200],
            "content": (n.get("content") or "")[:300],
            "matched_terms": n.get("matched_terms") or [],
            "rule_relevance": catalyst.get("relevance", 0),
            "date": n.get("date", ""),
            "source": n.get("source", ""),
        })

    return {
        "task": "agent_news_relevance",
        "fund_code": fund_code,
        "fund_name": fund_name,
        "instruction": (
            "逐条判断以下新闻与基金持仓是否有实质性投资关联（非泛泛关联）。"
            "实质性关联指：新闻事件直接影响其所持股票的基本面、估值、行业前景或市场情绪。"
            "仅标记能够影响持仓的新闻为 relevant。"
            "以下为泛泛关联（应标记为 irrelevant）："
            "- 新闻提到某公司发布手机但基金持半导体设备和芯片股"
            "- 新闻提到某车企发布新车但基金持上游半导体和材料股"
            "- 泛消费电子新闻与基金持仓无直接产业链关联"
        ),
        "holdings": holdings_payload,
        "candidate_news": candidate_news,
        "expected_output": {
            "relevant_news_ids": [1, 3, 5],
            "per_news_reasons": {
                "2": "小米手机发布与基金持有的美股半导体无直接关联",
                "4": "YU7汽车发布与基金持仓无交集",
            },
        },
    }
