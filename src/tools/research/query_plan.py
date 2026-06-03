"""Deterministic research query planning helpers.

No network calls, no provider SDKs, no data fetching.
Generates query plans that the host may use to drive news_research
and sentiment_analysis skills. The host decides whether to execute.

Outputs are fully JSON-serializable and deterministic.

Query prioritization:
- Portfolio positions are sorted by current_value or weight descending.
- Holdings are sorted by weight descending.
- Fund-level queries are generated first, then holdings, then
  themes/industries within the budget.
- Deduplication runs across all query types.
"""

from __future__ import annotations

from typing import Any


# Max query count to prevent explosion for large portfolios
_DEFAULT_MAX_QUERIES = 30
_DEFAULT_MAX_SENTIMENT_QUERIES = 15
_DEFAULT_PER_FUND_HOLDING_LIMIT = 5


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
    per_fund_holding_limit = int(opts.get("per_fund_holding_limit", _DEFAULT_PER_FUND_HOLDING_LIMIT))
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
    seen_news: set[str] = set()
    sentiment_queries: list[str] = []
    seen_sentiment: set[str] = set()
    query_entities: set[str] = set()
    query_themes: list[str] = []
    query_industries: list[str] = []

    # News query counters for budget tracking
    generated_news = 0
    dropped_news = 0
    generated_sentiment = 0
    dropped_sentiment = 0

    def _add_news(query: str) -> bool:
        nonlocal generated_news, dropped_news
        if len(news_queries) >= max_news:
            dropped_news += 1
            return False
        key = query.lower().strip()
        if key in seen_news:
            return False
        seen_news.add(key)
        news_queries.append(query)
        generated_news += 1
        return True

    def _add_sentiment(query: str) -> bool:
        nonlocal generated_sentiment, dropped_sentiment
        if len(sentiment_queries) >= max_sentiment:
            dropped_sentiment += 1
            return False
        key = query.lower().strip()
        if key in seen_sentiment:
            return False
        seen_sentiment.add(key)
        sentiment_queries.append(query)
        generated_sentiment += 1
        return True

    # --- Sort positions by current_value / weight descending ---
    def _position_sort_key(p: dict[str, Any]) -> float:
        return p.get("current_value", p.get("weight", 0.0) or 0.0) or 0.0

    sorted_positions = sorted(
        [p for p in position_list if isinstance(p, dict)],
        key=_position_sort_key,
        reverse=True,
    )

    # --- Collect entities from positions ---
    fund_codes: list[str] = []
    fund_names: list[str] = []

    for pos in sorted_positions:
        fc = pos.get("fund_code", "")
        if fc and fc not in fund_codes:
            fund_codes.append(fc)
        fn = pos.get("fund_name", "")
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
            "required_capabilities": [],
            "query_budget_summary": {
                "max_news_queries": max_news,
                "generated_news_queries": 0,
                "dropped_news_queries": 0,
                "max_sentiment_queries": max_sentiment,
                "generated_sentiment_queries": 0,
                "dropped_sentiment_queries": 0,
            },
            "warnings": warnings,
        }

    # --- Fund-level news queries ---
    if include_fund:
        for fc in fund_codes:
            profile = profile_map.get(fc, {})
            fname = profile.get("name", "") or fc
            _add_news(f"基金 {fc} {fname} 最新动态 业绩 表现")
            query_entities.add(fc)

        for fn in fund_names:
            existing = [profile_map.get(fc, {}).get("name", "") for fc in fund_codes]
            if fn not in existing:
                _add_news(f"基金 {fn} 最新消息 持仓")
                query_entities.add(fn)

    # --- Manager-level news queries ---
    if include_manager:
        managers_seen: set[str] = set()
        for fc in fund_codes:
            profile = profile_map.get(fc, {})
            manager = profile.get("manager", "")
            if manager and manager not in managers_seen:
                managers_seen.add(manager)
                _add_news(f"基金经理 {manager} 最新动态 投资观点")
                query_entities.add(manager)

    # --- Holdings-level queries (sorted by weight descending, per-fund limit) ---
    if holding_map:
        all_holdings: list[tuple[str, str, float, str | None]] = []  # (fund_code, name, weight, ticker)
        for fc in fund_codes:
            fund_holdings = holding_map.get(fc, [])
            sorted_holdings = sorted(
                [h for h in fund_holdings if isinstance(h, dict)],
                key=lambda h: h.get("weight", 0.0) or 0.0,
                reverse=True,
            )
            for h in sorted_holdings[:per_fund_holding_limit]:
                name = h.get("name", "")
                weight = h.get("weight", 0.0) or 0.0
                ticker = h.get("ticker")
                if name:
                    all_holdings.append((fc, name, weight, ticker))

        # Sort all holdings by weight descending (cross-fund)
        all_holdings.sort(key=lambda x: x[2], reverse=True)

        for _fc, name, _weight, ticker in all_holdings:
            q = f"{name}"
            if ticker:
                q += f" {ticker}"
            q += " 最新消息 财务 业绩"
            _add_news(q)
            query_entities.add(name)

    # --- Theme queries ---
    for theme in theme_list:
        if theme not in query_themes:
            query_themes.append(theme)
        _add_news(f"{theme} 投资主题 最新趋势 政策 行业")
        _add_sentiment(f"{theme} 市场情绪 投资者观点")

    # --- Industry queries ---
    for ind in industry_list:
        if ind not in query_industries:
            query_industries.append(ind)
        _add_news(f"{ind} 行业 最新动态 政策 龙头企业")

    # --- Macro queries ---
    if include_macro:
        macro_topics = [
            "中国宏观经济 央行政策 利率",
            "A股市场 流动性 资金面",
            "基金市场 资金流向 行业配置",
        ]
        for topic in macro_topics:
            _add_news(topic)

    # --- Fund-level sentiment queries ---
    for fc in fund_codes:
        profile = profile_map.get(fc, {})
        fname = profile.get("name", "") or fc
        _add_sentiment(f"基金 {fc} {fname} 市场情绪 评价 讨论")

    # --- KG context enrichment ---
    kg_entities = kg.get("entities", [])
    if kg_entities:
        for ent in kg_entities:
            if isinstance(ent, dict):
                ent_name = ent.get("name", ent.get("entity_id", ""))
            elif isinstance(ent, str):
                ent_name = ent
            else:
                continue
            if ent_name:
                query_entities.add(ent_name)

    # Determine required capabilities
    required_capabilities = []
    if news_queries:
        required_capabilities.extend(["web_search", "financial_news"])
    if sentiment_queries:
        if "social_sentiment" not in required_capabilities:
            required_capabilities.append("social_sentiment")
    required_capabilities = sorted(set(required_capabilities))

    if not news_queries:
        warnings.append("no news queries generated; supply positions, themes, or industries")

    return {
        "news_queries": news_queries,
        "sentiment_queries": sentiment_queries,
        "entities": sorted(query_entities),
        "themes": sorted(set(query_themes)),
        "industries": sorted(set(query_industries)),
        "required_capabilities": required_capabilities,
        "query_budget_summary": {
            "max_news_queries": max_news,
            "generated_news_queries": generated_news,
            "dropped_news_queries": dropped_news,
            "max_sentiment_queries": max_sentiment,
            "generated_sentiment_queries": generated_sentiment,
            "dropped_sentiment_queries": dropped_sentiment,
        },
        "warnings": warnings,
    }
