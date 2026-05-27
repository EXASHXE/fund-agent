"""新闻流水线调度入口 —— 持仓驱动定向采集 → 去重 → 蒸馏 → 简报

用法：
    from src.news.pipeline import run_news_pipeline

    results = run_news_pipeline(analyzer, config, agent_news_plan=None)
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import List, Dict
from src.news.entity_mapper import entity_profile_from_fund, all_search_terms
from src.news.deduplicator import exact_dedup, semantic_dedup, event_level_dedup
from src.news.catalyst import compute_catalyst_score, aggregate_fund_brief
from src.news.evaluator import evaluate_news_result, filter_relevant_catalysts


def run_news_pipeline(
    analyzer,
    config,
    agent_news_plan: Dict = None,
    days: int = 7,
    report_date=None,
    max_workers: int = None,
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
    as_of_date = report_date or date.today()
    if not isinstance(as_of_date, date):
        as_of_date = datetime.strptime(str(as_of_date)[:10], "%Y-%m-%d").date()

    holdings = list(getattr(config, "holdings", []) or [])
    if not holdings:
        return []

    worker_count = _resolve_news_workers(max_workers, len(holdings))
    if worker_count <= 1:
        return [
            _run_single_fund_news_pipeline(
                analyzer, holding, agent_news_plan, days, as_of_date
            )
            for holding in holdings
        ]

    results: List[Dict] = [None] * len(holdings)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_index = {
            executor.submit(
                _run_single_fund_news_pipeline,
                analyzer,
                holding,
                agent_news_plan,
                days,
                as_of_date,
            ): idx
            for idx, holding in enumerate(holdings)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            holding = holdings[idx]
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = _empty_news_result(
                    getattr(holding, "code", ""),
                    getattr(holding, "name", ""),
                    None,
                    as_of_date,
                    status="error",
                    error=str(exc),
                )
    return results


def _run_single_fund_news_pipeline(
    analyzer,
    holding,
    agent_news_plan: Dict,
    days: int,
    as_of_date: date,
) -> Dict:
    from src.news.news_fetcher import fetch_fund_news
    from src.news.sentiment import analyze_sentiment, daily_sentiment_aggregate
    from src.news.correlate import news_nav_correlation
    from src.news.agent_context import build_news_judgment_context, build_news_relevance_task
    from src.services.news_service import build_nav_summary, planned_news_keywords

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
    planned_keywords = planned_news_keywords(agent_news_plan, code)
    stock_keywords = all_search_terms(entity)
    combined_keywords = list(dict.fromkeys((planned_keywords or []) + stock_keywords[:15]))

    fetched_news = fetch_fund_news(
        code, name,
        keywords=combined_keywords if combined_keywords else None,
        days=days,
        fund_type=getattr(holding, "type", ""),
        as_of=as_of_date,
    )
    news_list, post_cutoff_news, undated_news = _partition_news_as_of(fetched_news, as_of_date)

    if not news_list:
        return _empty_news_result(
            code,
            name,
            entity,
            as_of_date,
            post_cutoff_news=post_cutoff_news,
            undated_news=undated_news,
            status="empty",
        )

    # === Step 3: 多层去重 ===
    news_list = exact_dedup(news_list)
    news_list = semantic_dedup(news_list)
    news_list = event_level_dedup(news_list)

    # === Step 4: 情绪分析（兼容旧模块）===
    news_with_sent = analyze_sentiment(news_list, holding_keywords=stock_keywords)
    daily_agg = daily_sentiment_aggregate(news_with_sent)

    # === Step 5: 催化分析（新模块）===
    catalyst_news = compute_catalyst_score(news_list, entity)
    scoring_catalyst_news = filter_relevant_catalysts(catalyst_news, min_relevance=0.2)
    today_str = as_of_date.isoformat()
    brief = aggregate_fund_brief(code, name, scoring_catalyst_news, today_str)
    news_evaluation = evaluate_news_result({
        "news_list": news_with_sent,
        "catalyst_news": catalyst_news,
    }, as_of=today_str, entity_profile=entity)

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
    sentiment_mean = (
        daily_agg[-1].get("decayed_sentiment_final", daily_agg[-1]["sentiment_mean"])
        if daily_agg else 0.5
    )
    nav_summary = build_nav_summary(nav_returns)

    agent_news_context = build_news_judgment_context(
        fund_name=name,
        fund_code=code,
        news_list=news_with_sent,
        daily_aggregates=daily_agg,
        nav_summary=nav_summary,
    )

    return {
        "fund_code": code,
        "fund_name": name,
        "news_count": len(catalyst_news),
        "sentiment_mean": sentiment_mean,
        "daily_aggregates": daily_agg,
        "correlation": corr,
        "news_list": news_with_sent,
        "post_cutoff_news": post_cutoff_news,
        "undated_news": undated_news,
        "catalyst_news": catalyst_news,
        "brief": brief,
        "news_evaluation": news_evaluation,
        "entity_profile": entity,
        "agent_news_context": agent_news_context,
        "relevance_task": build_news_relevance_task(name, code, entity, catalyst_news),
        "status": "ok",
    }


def _resolve_news_workers(max_workers: int, holding_count: int) -> int:
    if holding_count <= 1:
        return 1
    if max_workers is None:
        max_workers = min(4, holding_count)
    try:
        return max(1, min(int(max_workers), holding_count))
    except (TypeError, ValueError):
        return min(4, holding_count)


def _empty_news_result(
    code: str,
    name: str,
    entity,
    as_of_date,
    post_cutoff_news=None,
    undated_news=None,
    status: str = "empty",
    error: str = None,
) -> Dict:
    payload = {
        "fund_code": code,
        "fund_name": name,
        "news_count": 0,
        "sentiment_mean": 0.5,
        "daily_aggregates": [],
        "correlation": 0.0,
        "news_list": [],
        "post_cutoff_news": post_cutoff_news or [],
        "undated_news": undated_news or [],
        "entity_profile": entity,
        "catalyst_news": [],
        "brief": None,
        "news_evaluation": evaluate_news_result(
            {"news_list": [], "catalyst_news": []},
            as_of=as_of_date,
            entity_profile=entity,
        ),
        "status": status,
    }
    if error:
        payload["error"] = error
    return payload


def _partition_news_as_of(news_list: List[Dict], as_of_date) -> tuple:
    """Split news into report evidence, future observations and undated samples."""
    from datetime import datetime

    as_of_news = []
    post_cutoff_news = []
    undated_news = []
    for item in news_list or []:
        raw = str(item.get("date") or item.get("publish_date") or "")[:10]
        try:
            item_date = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            undated_news.append(item)
            continue
        if item_date <= as_of_date:
            as_of_news.append(item)
        else:
            post_cutoff_news.append(item)
    return as_of_news, post_cutoff_news, undated_news
