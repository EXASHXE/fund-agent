"""新闻流水线调度入口 —— 持仓驱动定向采集 → 去重 → 蒸馏 → 简报

用法：
    from legacy.news.pipeline import run_news_pipeline

    results = run_news_pipeline(analyzer, config, agent_news_plan=None)
"""

import hashlib
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import List, Dict
from legacy.deprecated.entity_mapper import entity_profile_from_fund, all_search_terms
from legacy.deprecated.catalyst import compute_catalyst_score, aggregate_fund_brief
from legacy.deprecated.evaluator import evaluate_news_result, filter_relevant_catalysts


def run_news_pipeline(
    analyzer,
    config,
    agent_news_plan: Dict = None,
    days: int = 7,
    report_date=None,
    max_workers: int = None,
) -> list[Dict]:
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

    results: list[Dict] = [None] * len(holdings)
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
    from legacy.news.news_fetcher import fetch_fund_news
    from legacy.deprecated.sentiment import analyze_sentiment, daily_sentiment_aggregate
    from legacy.news.agent_context import build_news_judgment_context, build_news_relevance_task
    from legacy.services.news_service import build_nav_summary, planned_news_keywords

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
    news_list = _exact_dedup(news_list)
    news_list = _semantic_dedup(news_list)
    news_list = _event_level_dedup(news_list)

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

    corr = _news_nav_correlation(daily_agg, nav_returns) if nav_returns else {}
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


def _partition_news_as_of(news_list: list[Dict], as_of_date) -> tuple:
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


def _news_nav_correlation(
    sentiment_daily: list,
    nav_daily_returns: list,
    lag_days: list | None = None,
) -> dict:
    if lag_days is None:
        lag_days = [0, 1, 3, 5]

    try:
        from scipy.stats import spearmanr
    except ImportError:
        return {lag: (0.0, 1.0) for lag in lag_days}

    from datetime import timedelta

    sent_map = {item["date"]: item["sentiment_mean"] for item in sentiment_daily}

    results = {}
    for lag in lag_days:
        pairs = []
        for nav_date, nav_return in nav_daily_returns:
            sent_date_str = (nav_date - timedelta(days=lag)).isoformat()
            if sent_date_str in sent_map:
                pairs.append((sent_map[sent_date_str], nav_return))

        if len(pairs) >= 5:
            r, p = spearmanr([p[0] for p in pairs], [p[1] for p in pairs])
            results[lag] = (round(r, 4), round(p, 4))
        else:
            results[lag] = (0.0, 1.0)

    return results


def _normalize_title(title: str) -> str:
    if not title:
        return ""
    t = title.strip()
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[，,。\.！!？?\s\"\"''「」『』【】\[\]{}()（）《》]", "", t)
    return t.lower()


def _exact_dedup(news_list: list, seen: set | None = None) -> list:
    if seen is None:
        seen = set()
    result = []
    for item in news_list:
        title = _normalize_title(item.get("title", ""))
        key = hashlib.md5(title.encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _semantic_dedup(news_list: list, threshold: float = 0.85) -> list:
    if len(news_list) <= 1:
        return news_list

    texts = [_normalize_title(item.get("title", "")) for item in news_list]
    keep = [True] * len(news_list)

    for i in range(len(texts)):
        if not keep[i]:
            continue
        words_i = set(texts[i])
        if not words_i:
            continue
        for j in range(i + 1, len(texts)):
            if not keep[j]:
                continue
            words_j = set(texts[j])
            if not words_j:
                continue
            intersection = words_i & words_j
            union = words_i | words_j
            sim = len(intersection) / len(union) if union else 0
            if sim >= threshold:
                keep[j] = False

    return [item for item, kept in zip(news_list, keep) if kept]


def _event_level_dedup(news_list: list, time_window_hours: int = 6) -> list:
    if len(news_list) <= 1:
        return news_list

    grouped = defaultdict(list)
    for item in news_list:
        title = item.get("title", "")
        date_key = item.get("date", "") or item.get("publish_date", "") or ""
        entity_hits = item.get("entity_hits", []) or item.get("matched_terms", [])
        if entity_hits:
            key = (date_key, tuple(sorted(entity_hits[:3])))
        else:
            key = (date_key, _normalize_title(title))
        grouped[key].append(item)

    result = []
    for items in grouped.values():
        result.append(items[0])
    return result
