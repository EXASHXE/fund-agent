"""新闻流水线调度入口 —— 持仓驱动定向采集 → 去重 → 蒸馏 → 简报

用法：
    from src.news.pipeline import run_news_pipeline

    results = run_news_pipeline(analyzer, config, agent_news_plan=None)
"""

from typing import List, Dict
from src.news.entity_mapper import entity_profile_from_fund, all_search_terms
from src.news.deduplicator import exact_dedup, semantic_dedup, event_level_dedup
from src.news.catalyst import compute_catalyst_score, aggregate_fund_brief
from src.news.evaluator import evaluate_news_result, filter_relevant_catalysts
from src.news.schemas import EntityProfile


def run_news_pipeline(
    analyzer,
    config,
    agent_news_plan: Dict = None,
    days: int = 7,
) -> List[Dict]:
    """运行完整新闻流水线：持仓画像 → 定向采集 → 去重 → 蒸馏 → 简报。

    Args:
        analyzer: FundAnalyzer 实例（含已加载的 funds 数据）
        config: PortfolioConfig 实例
        agent_news_plan: Agent 提供的新闻关键词计划
        days: 回溯天数

    Returns:
        per-fund 结果列表，兼容旧的 _run_news_analysis 返回格式，
        但每项额外包含 catalyst、brief 等新字段。
    """
    from src.news.news_fetcher import fetch_fund_news
    from src.news.sentiment import analyze_sentiment, daily_sentiment_aggregate
    from src.news.correlate import news_nav_correlation
    from src.cli import _planned_news_keywords, _build_nav_summary
    from src.news.agent_context import build_news_judgment_context
    from datetime import date

    results = []
    global_seen = set()

    for holding in config.holdings:
        code = holding.code
        name = holding.name
        fund_data = analyzer.funds.get(code, {})

        # === Step 1: 构建实体画像 ===
        holdings_raw = fund_data.get("holdings", [])
        holdings_list = []
        if holdings_raw is None:
            holdings_list = []
        elif hasattr(holdings_raw, "to_dict"):
            holdings_list = holdings_raw.to_dict("records")
        elif isinstance(holdings_raw, list):
            holdings_list = holdings_raw

        sectors_raw = fund_data.get("sectors", [])
        sectors_list = []
        if sectors_raw is None:
            sectors_list = []
        elif hasattr(sectors_raw, "to_dict"):
            sectors_list = sectors_raw.to_dict("records")
        elif isinstance(sectors_raw, list):
            sectors_list = sectors_raw

        entity = entity_profile_from_fund(code, name, holdings_list, sectors_list)

        # === Step 2: 定向采集 ===
        planned_keywords = _planned_news_keywords(agent_news_plan, code)
        stock_keywords = all_search_terms(entity)
        combined_keywords = list(dict.fromkeys((planned_keywords or []) + stock_keywords[:15]))

        news_list = fetch_fund_news(
            code, name,
            keywords=combined_keywords if combined_keywords else None,
            days=days,
            fund_type=getattr(holding, "type", ""),
            shared_seen=global_seen,
        )

        if not news_list:
            results.append({
                "fund_code": code,
                "fund_name": name,
                "news_count": 0,
                "sentiment_mean": 0.5,
                "daily_aggregates": [],
                "correlation": 0.0,
                "news_list": [],
                "entity_profile": entity,
                "catalyst_news": [],
                "brief": None,
                "news_evaluation": evaluate_news_result({"news_list": [], "catalyst_news": []}),
                "status": "empty",
            })
            continue

        # === Step 3: 多层去重 ===
        news_list = exact_dedup(news_list, global_seen)
        news_list = semantic_dedup(news_list)
        news_list = event_level_dedup(news_list)

        # === Step 4: 情绪分析（兼容旧模块）===
        news_with_sent = analyze_sentiment(news_list)
        daily_agg = daily_sentiment_aggregate(news_with_sent)

        # === Step 5: 催化分析（新模块）===
        catalyst_news = compute_catalyst_score(news_list, entity)
        scoring_catalyst_news = filter_relevant_catalysts(catalyst_news, min_relevance=0.2)
        today_str = date.today().isoformat()
        brief = aggregate_fund_brief(code, name, scoring_catalyst_news, today_str)
        news_evaluation = evaluate_news_result({
            "news_list": news_with_sent,
            "catalyst_news": catalyst_news,
        }, as_of=today_str)

        # === 兼容旧输出 ===
        nav_df = fund_data.get("nav", None)
        nav_returns = []
        if nav_df is not None and not (hasattr(nav_df, "empty") and nav_df.empty):
            if hasattr(nav_df, "index"):
                for idx, row in nav_df.iterrows():
                    d = idx.date() if hasattr(idx, "date") else idx
                    r = row.get("日增长率", 0)
                    if r and not (hasattr(r, "__isnan__") and r != r):
                        nav_returns.append((d, float(r)))

        corr = news_nav_correlation(daily_agg, nav_returns) if nav_returns else {}
        sentiment_mean = daily_agg[-1]["sentiment_mean"] if daily_agg else 0.5
        nav_summary = _build_nav_summary(nav_returns)

        agent_news_context = build_news_judgment_context(
            fund_name=name,
            fund_code=code,
            news_list=news_with_sent,
            daily_aggregates=daily_agg,
            nav_summary=nav_summary,
        )

        results.append({
            "fund_code": code,
            "fund_name": name,
            "news_count": len(catalyst_news),
            "sentiment_mean": sentiment_mean,
            "daily_aggregates": daily_agg,
            "correlation": corr,
            "news_list": news_with_sent,
            "catalyst_news": catalyst_news,
            "brief": brief,
            "news_evaluation": news_evaluation,
            "entity_profile": entity,
            "agent_news_context": agent_news_context,
            "status": "ok",
        })

    return results
