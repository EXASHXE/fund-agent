"""News service boundary for CLI, pipeline, and future Agent tools."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.config.shared import today as shared_today


def news_context_by_code(news_data: Sequence[Mapping[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """Build compact per-fund news context for scoring and Agent review."""
    contexts: dict[str, dict[str, Any]] = {}
    for item in news_data or []:
        code = item.get("fund_code")
        if not code:
            continue
        catalyst_news = item.get("catalyst_news") or []
        top_catalysts = sorted(
            catalyst_news,
            key=lambda n: abs((n.get("catalyst") or {}).get("weighted_score", 0)),
            reverse=True,
        )[:5]
        contexts[str(code)] = {
            "fund_code": code,
            "fund_name": item.get("fund_name", code),
            "status": item.get("status", ""),
            "news_count": item.get("news_count", 0),
            "sentiment_mean": item.get("sentiment_mean", 0.5),
            "daily_aggregates": (item.get("daily_aggregates") or [])[-5:],
            "brief": item.get("brief") or {},
            "news_evaluation": item.get("news_evaluation") or {},
            "top_catalysts": [
                {
                    "title": n.get("title", "")[:120],
                    "date": n.get("date", ""),
                    "event_type": (n.get("catalyst") or {}).get("event_type", ""),
                    "weighted_score": (n.get("catalyst") or {}).get("weighted_score", 0),
                    "relevance": (n.get("catalyst") or {}).get("relevance", 0),
                }
                for n in top_catalysts
            ],
        }
    return contexts


def planned_news_profile(agent_news_plan: Mapping[str, Any] | None, code: str) -> Mapping[str, Any]:
    if not agent_news_plan:
        return {}
    funds = agent_news_plan.get("funds") or {}
    return funds.get(code) or funds.get(str(code).zfill(6)) or {}


def planned_news_keywords(agent_news_plan: Mapping[str, Any] | None, code: str) -> list[str] | None:
    profile = planned_news_profile(agent_news_plan, code)
    keywords: list[str] = []
    for key in ("keywords", "search_terms", "expanded_keywords"):
        for kw in profile.get(key, []) or []:
            if kw and kw not in keywords:
                keywords.append(str(kw))

    split_keywords: list[str] = []
    for kw in keywords:
        for part in kw.split():
            part = part.strip()
            if len(part) >= 2 and part not in split_keywords:
                split_keywords.append(part)
    return split_keywords or None


def build_nav_summary(nav_returns) -> str:
    if not nav_returns:
        return "无净值收益率数据"
    latest = nav_returns[-1]
    recent = [ret for _, ret in nav_returns[-20:]]
    avg = sum(recent) / len(recent) if recent else 0
    return (
        f"最近净值日 {latest[0]}，日增长率 {latest[1]:+.2f}%；"
        f"近20个可用交易日平均日增长率 {avg:+.2f}%"
    )


def write_keyword_request_and_exit(config, codes, analyzer, output_path):
    """Write a news keyword request JSON and exit the current CLI command."""
    import json
    import sys

    from src.news.shared_fetch import cached_ak_call, normalize_company_name, pick_first

    request_file = (
        output_path[:-3] + ".news_keywords_request.json"
        if output_path.endswith(".md")
        else output_path + ".news_keywords_request.json"
    )
    print(f"\n[CLI] 未找到有效的新闻关键词缓存，生成请求文件: {request_file}")

    funds_data = {}
    for code in codes:
        fund_data = analyzer.funds.get(code, {})
        basic = fund_data.get("basic", {})
        name = basic.get("name", code)
        fund_type = basic.get("fund_type", "")

        top_holdings = []
        for year in ["2025", "2024"]:
            try:
                df = cached_ak_call("fund_portfolio_hold_em", symbol=code, date=year)
                if df is not None and not df.empty:
                    for _, row in df.head(10).iterrows():
                        stock_code = str(row.get("股票代码", "")).strip()
                        if not stock_code or stock_code.lower() == "nan":
                            continue
                        stock_name = normalize_company_name(str(row.get("股票名称", "")))
                        weight = pick_first(row, ["占净值比例", "持仓占比", "占比", "持股占比"])
                        top_holdings.append({
                            "stock_name": stock_name,
                            "stock_code": stock_code,
                            "weight": str(weight) if weight is not None else "",
                        })
                    break
            except Exception:
                continue

        funds_data[code] = {
            "name": name,
            "type": fund_type,
            "top_holdings": top_holdings,
        }

    request_payload = {
        "request_version": "news_keyword_request.v1",
        "generated_at": shared_today().isoformat(),
        "cache_path": "data/cache/news_keyword_profiles.json",
        "holding_codes": sorted(codes),
        "funds": funds_data,
    }

    with open(request_file, "w", encoding="utf-8") as handle:
        json.dump(request_payload, handle, ensure_ascii=False, indent=2)

    print("[CLI] 请使用 Agent 为该请求文件生成对应的关键词缓存，然后重新运行。")
    sys.exit(0)
