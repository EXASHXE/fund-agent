"""Deterministic research query planning helpers.

No network calls, no provider SDKs, no data fetching.
Generates query plans that the host may use to drive news_research
and sentiment_analysis skills. The host decides whether to execute.

Outputs are fully JSON-serializable and deterministic.
"""

from __future__ import annotations

from typing import Any


# Max query count to prevent explosion for large portfolios
_DEFAULT_MAX_QUERIES = 30
_DEFAULT_MAX_SENTIMENT_QUERIES = 15


def build_research_query_plan(
    portfolio_positions: list[dict[str, Any]] | None = None,
    holdings: dict[str, list[dict[str, Any]]] | None = None,
    fund_profiles: dict[str, dict[str, Any]] | None = None,
    themes: list[str] | None = None,
    industries: list[str] | None = None,
    kg_context: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic research query plan from portfolio/fund data.

    Args:
        portfolio_positions: List of portfolio position dicts.
        holdings: {fund_code: [{name, weight, industry, region, ticker}]}.
        fund_profiles: {fund_code: {name, fund_type, manager, benchmark}}.
        themes: Optional list of investment themes.
        industries: Optional list of industries to cover.
        kg_context: Optional KnowledgeGraph context if provided by host.
        options: Optional config:
            - max_news_queries (int): cap on news queries. Default 30.
            - max_sentiment_queries (int): cap on sentiment queries. Default 15.
            - include_fund_news (bool): include fund-level queries. Default True.
            - include_manager_news (bool): include manager queries. Default False.
            - include_macro_news (bool): include macro queries. Default False.

    Returns:
        {
            "news_queries": [string],
            "sentiment_queries": [string],
            "entities": [string],
            "themes": [string],
            "industries": [string],
            "required_capabilities": ["web_search", "financial_news", "social_sentiment"],
            "warnings": [...],
        }
    """
    opts = options or {}
    max_news = int(opts.get("max_news_queries", _DEFAULT_MAX_QUERIES))
    max_sentiment = int(opts.get("max_sentiment_queries", _DEFAULT_MAX_SENTIMENT_QUERIES))
    include_fund = opts.get("include_fund_news", True)
    include_manager = opts.get("include_manager_news", False)
    include_macro = opts.get("include_macro_news", False)

    position_list = portfolio_positions or []
    holding_map = holdings or {}
    profile_map = fund_profiles or {}
    theme_list = themes or []
    industry_list = industries or []
    kg = kg_context or {}

    warnings: list[str] = []
    news_queries: list[str] = []
    sentiment_queries: list[str] = []
    query_entities: list[str] = []
    query_themes: list[str] = []
    query_industries: list[str] = []

    # --- Collect entities from positions
    fund_codes: list[str] = []
    fund_names: list[str] = []

    for pos in position_list:
        fc = pos.get("fund_code", "") if isinstance(pos, dict) else ""
        if fc and fc not in fund_codes:
            fund_codes.append(fc)
        fn = pos.get("fund_name", "") if isinstance(pos, dict) else ""
        if fn and fn not in fund_names:
            fund_names.append(fn)

    if not fund_codes and not fund_names and not theme_list and not industry_list:
        warnings.append("no positions, themes, or industries provided; query plan is empty")
        return {
            "news_queries": [],
            "sentiment_queries": [],
            "entities": [],
            "themes": [],
            "industries": [],
            "required_capabilities": ["web_search", "financial_news", "social_sentiment"],
            "warnings": warnings,
        }

    # --- Fund-level news queries
    if include_fund:
        for fc in fund_codes:
            if len(news_queries) >= max_news:
                warnings.append(f"news query limit ({max_news}) reached; truncating")
                break
            profile = profile_map.get(fc, {})
            fname = profile.get("name", "") or fc
            # Chinese fund news query
            news_queries.append(f"基金 {fc} {fname} 最新动态 业绩 表现")
            query_entities.append(fc)

        for fn in fund_names:
            if len(news_queries) >= max_news:
                break
            if fn not in [profile_map.get(fc, {}).get("name", "") for fc in fund_codes]:
                news_queries.append(f"基金 {fn} 最新消息 持仓")
                query_entities.append(fn)

    # --- Manager-level news queries
    if include_manager:
        managers_seen: set[str] = set()
        for fc in fund_codes:
            if len(news_queries) >= max_news:
                break
            profile = profile_map.get(fc, {})
            manager = profile.get("manager", "")
            if manager and manager not in managers_seen:
                managers_seen.add(manager)
                news_queries.append(f"基金经理 {manager} 最新动态 投资观点")
                query_entities.append(manager)

    # --- Holdings-level queries
    if holding_map:
        holding_names_seen: set[str] = set()
        for fc in fund_codes:
            if len(news_queries) >= max_news:
                break
            fund_holdings = holding_map.get(fc, [])
            for h in fund_holdings:
                if len(news_queries) >= max_news:
                    break
                if not isinstance(h, dict):
                    continue
                name = h.get("name", "")
                ticker = h.get("ticker", "")
                if name and name not in holding_names_seen:
                    holding_names_seen.add(name)
                    q = f"{name}"
                    if ticker:
                        q += f" {ticker}"
                    q += " 最新消息 财务 业绩"
                    news_queries.append(q)
                    query_entities.append(name)

    # --- Theme queries
    if theme_list:
        for theme in theme_list:
            if len(news_queries) >= max_news:
                break
            if theme not in query_themes:
                query_themes.append(theme)
            news_queries.append(f"{theme} 投资主题 最新趋势 政策 行业")
            sentiment_queries.append(f"{theme} 市场情绪 投资者观点")

    # --- Industry queries
    if industry_list:
        for ind in industry_list:
            if len(news_queries) >= max_news:
                break
            if ind not in query_industries:
                query_industries.append(ind)
            news_queries.append(f"{ind} 行业 最新动态 政策 龙头企业")

    # --- Macro queries
    if include_macro:
        macro_topics = [
            "中国宏观经济 央行政策 利率",
            "A股市场 流动性 资金面",
            "基金市场 资金流向 行业配置",
        ]
        for topic in macro_topics:
            if len(news_queries) >= max_news:
                break
            news_queries.append(topic)

    # --- Sentiment queries
    # Deduplicate and cap
    seen_sentiment: set[str] = set()
    trimmed_sentiment: list[str] = []
    for q in sentiment_queries:
        if len(trimmed_sentiment) >= max_sentiment:
            warnings.append(f"sentiment query limit ({max_sentiment}) reached; truncating")
            break
        if q not in seen_sentiment:
            seen_sentiment.add(q)
            trimmed_sentiment.append(q)

    # Add fund-level sentiment queries if not done yet
    if not trimmed_sentiment and fund_codes:
        for fc in fund_codes:
            if len(trimmed_sentiment) >= max_sentiment:
                break
            profile = profile_map.get(fc, {})
            fname = profile.get("name", "") or fc
            trimmed_sentiment.append(f"基金 {fc} {fname} 市场情绪 评价 讨论")

    # --- KG context enrichment
    kg_entities = kg.get("entities", [])
    if kg_entities:
        for ent in kg_entities:
            if isinstance(ent, dict):
                ent_name = ent.get("name", ent.get("entity_id", ""))
            elif isinstance(ent, str):
                ent_name = ent
            else:
                continue
            if ent_name and ent_name not in query_entities:
                query_entities.append(ent_name)

    # Determine required capabilities
    required_capabilities = []
    if news_queries:
        required_capabilities.extend(["web_search", "financial_news"])
    if trimmed_sentiment:
        required_capabilities.append("social_sentiment")

    # Deduplicate
    required_capabilities = sorted(set(required_capabilities))

    # If no data at all to query
    if not news_queries:
        warnings.append("no news queries generated; supply positions, themes, or industries")

    return {
        "news_queries": news_queries,
        "sentiment_queries": trimmed_sentiment,
        "entities": sorted(set(query_entities)),
        "themes": sorted(set(query_themes)),
        "industries": sorted(set(query_industries)),
        "required_capabilities": required_capabilities,
        "warnings": warnings,
    }
