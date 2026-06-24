#!/usr/bin/env python3
"""Build news snapshot from KG context, portfolio input, and optional provider data.

Reads knowledge_graph_context.private.json (required), portfolio_input (optional
fallback), and provider_snapshot (optional).  Attempts to fetch news from
available providers (Tavily, Bocha, SerpAPI, Finnhub) using API keys from
environment variables only.

Gracefully degrades when no API keys are available — produces an empty snapshot
with appropriate missing-data markers.

FORBIDDEN:
- No fabricated news items
- No search failures reported as news conclusions
- No API keys written to any file, log, or output
- No provider SDK imports at module level (lazy imports only)
- No network requests when no API keys are set
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_QUERIES = 30
MAX_TOTAL_ITEMS = 80
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_MAX_RESULTS_PER_QUERY = 5

# Provider priority
DEFAULT_PROVIDER_PRIORITY = ["tavily", "bocha", "serpapi", "finnhub"]

# ---------------------------------------------------------------------------
# Query planning
# ---------------------------------------------------------------------------

# Theme → specific query templates
_THEME_QUERIES: dict[str, list[str]] = {
    "半导体": ["半导体 芯片 行情", "半导体 政策 产业", "AI算力 芯片 需求"],
    "CPO": ["CPO 光模块 产业链", "光通信 CPO 技术"],
    "创新药": ["创新药 审批 临床", "医药 集采 政策"],
    "ASCO": ["ASCO 肿瘤 学术", "抗癌 新药 临床"],
    "QDII": ["QDII 海外 投资", "全球市场 行情", "美元 汇率"],
    "纳斯达克": ["纳斯达克 科技股 行情", "美股 纳指 走势"],
    "红利低波": ["红利 高股息 策略", "利率 债券 收益"],
    "短债": ["短债 基金 收益", "债券 信用 风险", "利率 资金面"],
    "标普500": ["标普500 行情 走势", "美股 大盘 分析"],
    "油气": ["原油 价格 OPEC", "油气 能源 供需"],
    "电池": ["锂电池 产业链", "储能 电池 技术", "新能源车 锂电 需求"],
    "现金/余额宝/稳健理财": ["货币基金 收益", "余额宝 利率", "稳健理财 收益率"],
}

# Topic → keywords for detecting fund-name/topic overlap (used for theme deprecation)
_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "半导体": ["半导体", "芯片", "集成电路", "晶圆", "封测", "光刻"],
    "CPO": ["CPO", "光模块", "光通信", "光电"],
    "创新药": ["创新药", "医药", "生物", "药", "医疗", "临床"],
    "ASCO": ["ASCO", "肿瘤", "抗癌", "oncology"],
    "QDII": ["QDII", "海外", "全球", "国际", "美元"],
    "纳斯达克": ["纳斯达克", "NASDAQ", "纳指", "美股", "科技股"],
    "红利低波": ["红利", "低波", "高股息", "分红", "价值"],
    "短债": ["短债", "债券", "纯债", "利率债", "信用债"],
    "标普500": ["标普", "S&P", "SP500", "500"],
    "油气": ["油气", "石油", "原油", "OPEC", "能源", "天然气"],
    "电池": ["电池", "锂电", "储能", "钠电", "固态电池", "新能源车"],
    "现金/余额宝/稳健理财": ["现金", "余额宝", "货币", "理财", "稳健"],
}


def _build_query_plan(kg_context: dict, portfolio_input: dict | None) -> list[dict]:
    """Build a query plan from KG entities and watch topics.

    Uses the new prioritized query plan from KG context if available,
    otherwise falls back to the legacy query building logic.
    """
    queries: list[dict] = []

    # Check if KG context has new-style query plan with priorities
    kg_plan = kg_context.get("query_plan", [])
    # Track topics covered by fund_name/fund_code queries for theme deprecation
    fund_covered_topics: set[str] = set()

    if kg_plan and any("query_type" in qp for qp in kg_plan):
        # New format with priorities - use directly with query expansion
        for qp in kg_plan:
            query_text = qp.get("query", "")
            if not query_text:
                continue

            query_type = qp.get("query_type", "theme_fallback")

            # Extract topic_tags from entities if not present
            topic_tags = qp.get("topic_tags", [])
            if not topic_tags:
                for ent in qp.get("entities", []):
                    if ent.startswith("macro:"):
                        topic_tags.append(ent.replace("macro:", ""))
                    elif ent.startswith("industry:"):
                        topic_tags.append(ent.replace("industry:", ""))

            # Query expansion for fund_name and fund_code types
            expanded_query = query_text
            if query_type == "fund_name":
                expanded_query = f"{query_text} 基金 行情"
                # Track which watch topics this fund_name covers
                for topic, keywords in _TOPIC_KEYWORDS.items():
                    for kw in keywords:
                        if kw.lower() in query_text.lower():
                            fund_covered_topics.add(topic)
                            break
            elif query_type == "fund_code":
                expanded_query = f"{query_text} 基金 净值"

            queries.append(
                {
                    "query_id": qp.get("query_id", hashlib.sha256(query_text.encode()).hexdigest()[:12]),
                    "query": expanded_query,
                    "query_type": query_type,
                    "priority": qp.get("priority", 5),
                    "entities": qp.get("entities", []),
                    "topic_tags": topic_tags,
                    "related_funds": qp.get("related_funds", []),
                    "reason": qp.get("reason", ""),
                    "source": qp.get("source", "unknown"),
                    "confidence": qp.get("confidence", "low"),
                    "fallback": qp.get("fallback", False),
                }
            )
    else:
        # Legacy format - build from scratch with new structure
        for qp in kg_plan:
            query_text = qp.get("query", "")
            entities = qp.get("entities", [])
            topic_tags = qp.get("topic_tags", [])
            if query_text:
                # Determine query type from entities
                query_type = "theme_fallback"
                if any(e.startswith("holding_") for e in entities):
                    query_type = "holding_company"
                elif any(e.startswith("benchmark:") for e in entities):
                    query_type = "benchmark"
                elif any(e.startswith("fund_manager:") for e in entities):
                    query_type = "fund_manager"
                elif any(e.startswith("fund_name:") for e in entities):
                    query_type = "fund_name"
                elif any(e.startswith("fund:") for e in entities):
                    query_type = "fund_code"
                elif any(e.startswith("industry:") for e in entities):
                    query_type = "sector"
                elif any(e.startswith("macro:") for e in entities):
                    query_type = "theme"

                # Query expansion for fund_name and fund_code types
                expanded_query = query_text
                if query_type == "fund_name":
                    expanded_query = f"{query_text} 基金 行情"
                    # Track which watch topics this fund_name covers
                    for topic, keywords in _TOPIC_KEYWORDS.items():
                        for kw in keywords:
                            if kw.lower() in query_text.lower():
                                fund_covered_topics.add(topic)
                                break
                elif query_type == "fund_code":
                    expanded_query = f"{query_text} 基金 净值"

                queries.append(
                    {
                        "query_id": qp.get("query_id", hashlib.sha256(query_text.encode()).hexdigest()[:12]),
                        "query": expanded_query,
                        "query_type": query_type,
                        "priority": 5,  # Default priority
                        "entities": entities,
                        "topic_tags": topic_tags,
                        "related_funds": [],
                        "reason": "",
                        "source": "legacy",
                        "confidence": "low",
                        "fallback": query_type == "theme_fallback",
                    }
                )

        # From fund_entities, add fund-specific queries
        for fe in kg_context.get("fund_entities", []):
            fund_code = fe.get("fund_code", "")
            fund_name = fe.get("fund_name", "")

            # Add fund_name query if not already present
            if fund_name:
                qid = hashlib.sha256(f"fund_name_{fund_name}".encode()).hexdigest()[:12]
                queries.append(
                    {
                        "query_id": qid,
                        "query": f"{fund_name} 基金 行情",
                        "query_type": "fund_name",
                        "priority": 2,
                        "entities": [f"fund_name:{fund_name}"],
                        "topic_tags": [],
                        "related_funds": [fund_name],
                        "reason": f"Fund name from portfolio: {fund_name}",
                        "source": "portfolio_input",
                        "confidence": "medium",
                        "fallback": False,
                    }
                )
                # Track which watch topics this fund_name covers
                for topic, keywords in _TOPIC_KEYWORDS.items():
                    for kw in keywords:
                        if kw.lower() in fund_name.lower():
                            fund_covered_topics.add(topic)
                            break

            # Add fund_code query if not already present
            if fund_code:
                qid = hashlib.sha256(f"fund_code_{fund_code}".encode()).hexdigest()[:12]
                queries.append(
                    {
                        "query_id": qid,
                        "query": f"{fund_code} 基金 净值",
                        "query_type": "fund_code",
                        "priority": 2,
                        "entities": [f"fund:{fund_code}"],
                        "topic_tags": [],
                        "related_funds": [fund_name] if fund_name else [],
                        "reason": f"Fund code from portfolio: {fund_code}",
                        "source": "portfolio_input",
                        "confidence": "medium",
                        "fallback": False,
                    }
                )

            # Theme queries: skip _THEME_QUERIES for topics already covered by fund_name/fund_code
            for topic in fe.get("theme_tags", []):
                if topic in fund_covered_topics:
                    continue  # Already covered by fund-specific query
                template_queries = _THEME_QUERIES.get(topic, [])
                for tq in template_queries:
                    qid = hashlib.sha256(f"{fund_code}_{tq}".encode()).hexdigest()[:12]
                    queries.append(
                        {
                            "query_id": qid,
                            "query": tq,
                            "query_type": "theme",
                            "priority": 3,
                            "entities": [f"fund:{fund_code}"] if fund_code else [],
                            "topic_tags": [topic],
                            "related_funds": [fe.get("fund_name", "")] if fund_code else [],
                            "reason": f"Theme query for {fund_code or fe.get('fund_name', '')}",
                            "source": "theme_template",
                            "confidence": "low",
                            "fallback": False,
                        }
                    )

        # From watch_topics, add macro queries for topics not yet covered
        covered_topics: set[str] = set()
        for q in queries:
            for t in q.get("topic_tags", []):
                covered_topics.add(t)
        # Also consider fund_covered_topics as covered
        covered_topics.update(fund_covered_topics)

        for topic in kg_context.get("watch_topics", []):
            if topic not in covered_topics:
                template_queries = _THEME_QUERIES.get(topic, [topic])
                for tq in template_queries[:1]:  # one query per uncovered topic
                    qid = hashlib.sha256(f"macro_{topic}_{tq}".encode()).hexdigest()[:12]
                    queries.append(
                        {
                            "query_id": qid,
                            "query": tq,
                            "query_type": "theme_fallback",
                            "priority": 5,
                            "entities": [f"macro:{topic}"],
                            "topic_tags": [topic],
                            "related_funds": [],
                            "reason": "Unmatched watch topic fallback",
                            "source": "fallback",
                            "confidence": "low",
                            "fallback": True,
                        }
                    )

    # Deduplicate by query_id
    seen: set[str] = set()
    deduped: list[dict] = []
    for q in queries:
        if q["query_id"] not in seen:
            deduped.append(q)
            seen.add(q["query_id"])

    # Sort by priority (lower number = higher priority)
    deduped.sort(key=lambda x: (x.get("priority", 5), x.get("query_id", "")))

    # Cap at MAX_QUERIES
    return deduped[:MAX_QUERIES]


# ---------------------------------------------------------------------------
# Provider implementations (lazy imports)
# ---------------------------------------------------------------------------


def _get_env_key(name: str) -> str | None:
    """Get an API key from environment, never log or print it."""
    val = os.environ.get(name)
    return val if val else None


def _provider_tavily(query: str, max_results: int) -> tuple[list[dict], str | None]:
    """Try Tavily search. Returns (items, error).

    Note: Does NOT disable SSL verification by default.
    If SSL fails, returns error without modifying verification settings.
    """
    api_key = _get_env_key("TAVILY_API_KEY")
    if not api_key:
        return [], "TAVILY_API_KEY not set"
    try:
        from tavily import TavilyClient  # type: ignore[import-untyped]

        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results, topic="news")
        items: list[dict] = []
        for r in response.get("results", []):
            items.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "source": r.get("source", ""),
                    "published_at": r.get("published_date", ""),
                    "summary": r.get("content", ""),
                }
            )
        return items, None
    except ImportError:
        return [], "tavily-python not installed"
    except Exception as exc:
        error_msg = str(exc)
        # Check for SSL errors - do not disable verification, just report error
        if "SSL" in error_msg or "certificate" in error_msg.lower():
            return [], f"SSL verification failed: {error_msg}"
        return [], error_msg


def _provider_bocha(query: str, max_results: int) -> tuple[list[dict], str | None]:
    """Try Bocha web search. Returns (items, error).

    Handles HTTP 405 errors gracefully by returning an appropriate error message.
    """
    api_key = _get_env_key("BOCHA_API_KEY")
    if not api_key:
        return [], "BOCHA_API_KEY not set"
    try:
        import json as _json
        import urllib.parse
        import urllib.request

        # Use POST method which is more commonly supported for search APIs
        params = _json.dumps({"q": query, "count": max_results, "freshness": "day"}).encode("utf-8")
        url = "https://api.bochaai.com/v1/web-search"
        req = urllib.request.Request(
            url,
            data=params,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        items: list[dict] = []
        for r in data.get("data", {}).get("webPages", {}).get("value", []):
            items.append(
                {
                    "title": r.get("name", ""),
                    "url": r.get("url", ""),
                    "source": r.get("siteName", r.get("provider", "")),
                    "published_at": r.get("dateLastCrawled", r.get("datePublished", "")),
                    "summary": r.get("snippet", ""),
                }
            )
        return items, None
    except urllib.error.HTTPError as exc:
        if exc.code == 405:
            return [], "HTTP 405: Method not allowed - Bocha API endpoint may require GET request"
        return [], f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:
        error_msg = str(exc)
        if "HTTP Error 405" in error_msg:
            return [], "HTTP 405: Method not allowed - Bocha API endpoint may require GET request"
        return [], error_msg


def _provider_serpapi(query: str, max_results: int) -> tuple[list[dict], str | None]:
    """Try SerpAPI Google search. Returns (items, error)."""
    api_key = _get_env_key("SERPAPI_API_KEY")
    if not api_key:
        return [], "SERPAPI_API_KEY not set"
    try:
        from serpapi import GoogleSearch  # type: ignore[import-untyped]

        search = GoogleSearch(
            {
                "q": query,
                "api_key": api_key,
                "num": max_results,
                "tbm": "nws",
            }
        )
        results = search.get_dict()
        items: list[dict] = []
        for r in results.get("news_results", []):
            items.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "source": r.get("source", ""),
                    "published_at": r.get("date", ""),
                    "summary": r.get("snippet", ""),
                }
            )
        return items, None
    except ImportError:
        return [], "google-search-results not installed"
    except Exception as exc:
        return [], str(exc)


def _provider_finnhub(query: str, symbol: str | None = None) -> tuple[list[dict], str | None]:
    """Try Finnhub company news. Returns (items, error).

    Finnhub requires a valid stock symbol. If no symbol is provided or the query
    doesn't contain a recognizable ticker, return 'skipped_no_symbol' status
    instead of an error.
    """
    api_key = _get_env_key("FINNHUB_API_KEY")
    if not api_key:
        return [], "FINNHUB_API_KEY not set"
    if not symbol:
        # Return special status indicating skip, not error
        return [], "skipped_no_symbol"
    try:
        import finnhub  # type: ignore[import-untyped]

        finnhub_client = finnhub.Client(api_key=api_key)
        from datetime import datetime, timedelta

        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        news = finnhub_client.company_news(symbol, _from=week_ago, to=today)
        items: list[dict] = []
        for r in news[:10]:
            items.append(
                {
                    "title": r.get("headline", ""),
                    "url": r.get("url", ""),
                    "source": r.get("source", ""),
                    "published_at": datetime.fromtimestamp(r.get("datetime", 0)).isoformat()
                    if r.get("datetime")
                    else "",
                    "summary": r.get("summary", r.get("headline", "")),
                }
            )
        return items, None
    except ImportError:
        return [], "finnhub-python not installed"
    except Exception as exc:
        return [], str(exc)


def _extract_ticker_from_entities(entities: list[str]) -> str | None:
    """Extract a valid stock ticker symbol from the entities list.

    Looks for ``holding_ticker:XXX`` entries and validates that XXX is a
    plausible US stock ticker (1-5 uppercase ASCII letters).  Returns the
    first valid ticker found, or None when no ticker is available.

    Chinese fund codes (e.g. ``fund:000001``) are deliberately excluded —
    they are not Finnhub symbols.
    """
    import re

    ticker_re = re.compile(r"^[A-Z]{1,5}$")

    for ent in entities:
        if not ent.startswith("holding_ticker:"):
            continue
        candidate = ent[len("holding_ticker:") :]
        if not candidate:
            continue
        # Normalise to uppercase for validation
        candidate_upper = candidate.upper()
        if ticker_re.match(candidate_upper):
            return candidate_upper
    return None


PROVIDER_FUNCS = {
    "tavily": lambda q, n: _provider_tavily(q, n),
    "bocha": lambda q, n: _provider_bocha(q, n),
    "serpapi": lambda q, n: _provider_serpapi(q, n),
    "finnhub": lambda q, n: _provider_finnhub(q),  # finnhub uses symbol not query
}


# ---------------------------------------------------------------------------
# News item normalization and deduplication
# ---------------------------------------------------------------------------


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/").lower()
    except Exception:
        return url.lower().rstrip("/")


def _news_item_id(title: str, url: str, source: str, published_at: str) -> str:
    """Generate stable hash ID for a news item."""
    raw = f"{title}|{url}|{source}|{published_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _compute_relevance_score(item: dict, query: str, topic_tags: list[str]) -> float:
    """Compute a deterministic relevance score (0.0–1.0)."""
    score = 0.5  # base
    title = item.get("title", "").lower()
    summary = item.get("summary", "").lower()
    text = f"{title} {summary}"

    # Boost if query keywords appear in title/summary
    for word in query.split():
        if word.lower() in text:
            score += 0.1

    # Boost for topic tag matches
    for tag in topic_tags:
        if tag.lower() in text:
            score += 0.05

    return min(round(score, 4), 1.0)


def _compute_freshness_score(published_at: str, lookback_days: int) -> float:
    """Compute freshness score based on publication date."""
    if not published_at:
        return 0.3
    try:
        # Try ISO format
        pub_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        age_days = (now - pub_date).days
        if age_days < 0:
            return 1.0
        if age_days <= lookback_days:
            return round(1.0 - (age_days / lookback_days) * 0.7, 4)
        return 0.1
    except (ValueError, TypeError):
        return 0.3


# Fallback confidence penalty constants
_FALLBACK_CONFIDENCE_MULTIPLIER = 0.5
_FALLBACK_RELEVANCE_MULTIPLIER = 0.5

# Confidence level demotion map for fallback items
_CONFIDENCE_LEVEL_DEMOTION: dict[str, str] = {
    "high": "medium",
    "medium": "low",
    "low": "very_low",
    "very_low": "very_low",
}


def _apply_fallback_confidence_penalty(item: dict) -> dict:
    """Apply confidence penalty to news items from fallback queries.

    When a query has fallback=True or query_type=theme_fallback, the resulting
    news items get a 0.5x penalty on relevance_score and confidence, and the
    confidence level is demoted. This prevents broad theme-level news from
    dominating the evidence base.

    Args:
        item: A news item dict with relevance_score, confidence, and
              is_fallback_query / query_type fields.

    Returns:
        The same item dict with penalized scores and fallback_confidence_applied flag.
    """
    is_fallback = item.get("is_fallback_query", False)
    query_type = item.get("query_type", "")

    if not is_fallback and query_type != "theme_fallback":
        return item

    # Apply 0.5x penalty to relevance_score
    item["relevance_score"] = round(item.get("relevance_score", 0.0) * _FALLBACK_RELEVANCE_MULTIPLIER, 4)

    # Apply 0.5x penalty to confidence (numeric)
    item["confidence"] = round(item.get("confidence", 0.0) * _FALLBACK_CONFIDENCE_MULTIPLIER, 4)

    # Demote confidence level if present
    confidence_level = item.get("confidence_level", "")
    if confidence_level in _CONFIDENCE_LEVEL_DEMOTION:
        item["confidence_level"] = _CONFIDENCE_LEVEL_DEMOTION[confidence_level]

    # Set flag indicating penalty was applied
    item["fallback_confidence_applied"] = True

    return item


def _detect_language(text: str) -> str:
    """Simple heuristic language detection."""
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    if chinese_chars > len(text) * 0.2:
        return "zh"
    return "en"


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def build_news_snapshot(
    kg_context: dict,
    portfolio_input: dict | None = None,
    provider_snapshot: dict | None = None,
) -> dict:
    """Build the news snapshot dict."""
    now = datetime.now(UTC).isoformat()

    # Read env configuration
    lookback_days = int(os.environ.get("FUND_AGENT_NEWS_LOOKBACK_DAYS", str(DEFAULT_LOOKBACK_DAYS)))
    max_results_per_query = int(
        os.environ.get("FUND_AGENT_MAX_NEWS_RESULTS_PER_QUERY", str(DEFAULT_MAX_RESULTS_PER_QUERY))
    )
    max_total_items = int(os.environ.get("FUND_AGENT_MAX_TOTAL_NEWS_ITEMS", str(MAX_TOTAL_ITEMS)))

    priority_str = os.environ.get("FUND_AGENT_DATA_PROVIDER_PRIORITY", "")
    if priority_str:
        provider_priority = [p.strip() for p in priority_str.split(",") if p.strip()]
    else:
        provider_priority = DEFAULT_PROVIDER_PRIORITY

    # Check API key availability
    provider_status: dict[str, dict[str, Any]] = {}
    any_key_available = False
    for pname in DEFAULT_PROVIDER_PRIORITY:
        key_map = {
            "tavily": "TAVILY_API_KEY",
            "bocha": "BOCHA_API_KEY",
            "serpapi": "SERPAPI_API_KEY",
            "finnhub": "FINNHUB_API_KEY",
        }
        has_key = bool(_get_env_key(key_map.get(pname, "")))
        provider_status[pname] = {
            "available": has_key,
            "error": None if has_key else f"{key_map.get(pname, '')} not set",
        }
        if has_key:
            any_key_available = True

    # Build query plan
    query_plan = _build_query_plan(kg_context, portfolio_input)

    # Execute queries against available providers
    all_items: list[dict] = []
    seen_urls: set[str] = set()
    seen_title_source: set[str] = set()
    coverage_gaps: list[str] = []

    for qp in query_plan:
        query = qp["query"]
        query_id = qp.get("query_id", "")
        query_type = qp.get("query_type", "theme_fallback")
        priority = qp.get("priority", 5)
        topic_tags = qp.get("topic_tags", [])
        entities = qp.get("entities", [])
        related_funds = qp.get("related_funds", [])
        reason = qp.get("reason", "")
        source = qp.get("source", "unknown")
        query_confidence = qp.get("confidence", "low")
        is_fallback = qp.get("fallback", False)
        provider_attempts: list[str] = []
        query_had_results = False
        query_error: str | None = None

        # Try providers in priority order
        ordered_providers = [p for p in provider_priority if p in PROVIDER_FUNCS]

        for pname in ordered_providers:
            if not provider_status.get(pname, {}).get("available", False):
                continue

            provider_attempts.append(pname)
            try:
                # Finnhub requires a valid stock ticker extracted from entities,
                # not the generic query text.
                if pname == "finnhub":
                    ticker = _extract_ticker_from_entities(entities)
                    items, error = _provider_finnhub(query, symbol=ticker)
                else:
                    items, error = PROVIDER_FUNCS[pname](query, max_results_per_query)
                if error:
                    # Handle skipped_no_symbol for Finnhub - not an error, just skip
                    if error == "skipped_no_symbol":
                        provider_status[pname]["status"] = "skipped"
                        continue
                    provider_status[pname]["error"] = error
                    continue

                for raw_item in items:
                    url = raw_item.get("url", "")
                    title = raw_item.get("title", "")
                    source = raw_item.get("source", "")
                    published_at = raw_item.get("published_at", "")

                    # Deduplicate by URL
                    norm_url = _normalize_url(url) if url else ""
                    if norm_url and norm_url in seen_urls:
                        continue
                    if norm_url:
                        seen_urls.add(norm_url)

                    # Deduplicate by title+source+published_at
                    dedup_key = f"{title}|{source}|{published_at}"
                    if dedup_key in seen_title_source:
                        continue
                    seen_title_source.add(dedup_key)

                    # Build normalized item with full query metadata
                    item_id = _news_item_id(title, url, source, published_at)
                    relevance = _compute_relevance_score(raw_item, query, topic_tags)
                    freshness = _compute_freshness_score(published_at, lookback_days)
                    lang = _detect_language(f"{title} {raw_item.get('summary', '')}")

                    # Combine query confidence with relevance/freshness
                    base_confidence = round(min(relevance, freshness), 4)
                    if query_confidence == "high":
                        final_confidence = min(base_confidence * 1.2, 1.0)
                    elif query_confidence == "medium":
                        final_confidence = base_confidence
                    else:
                        final_confidence = base_confidence * 0.8

                    news_item = {
                        "id": item_id,
                        "query_id": query_id,
                        "provider": pname,
                        "query": query,
                        "query_type": query_type,
                        "priority": priority,
                        "title": title,
                        "url": url,
                        "source": source,
                        "published_at": published_at,
                        "summary": raw_item.get("summary", ""),
                        "language": lang,
                        "related_entities": entities,
                        "related_funds": related_funds,
                        "topic_tags": topic_tags,
                        "reason": reason,
                        "source_type": source,
                        "relevance_score": relevance,
                        "freshness_score": freshness,
                        "confidence": round(final_confidence, 4),
                        "is_fallback_query": is_fallback,
                    }

                    # Apply fallback confidence penalty for fallback queries
                    news_item = _apply_fallback_confidence_penalty(news_item)

                    all_items.append(news_item)
                    query_had_results = True

            except Exception as exc:
                provider_status[pname]["error"] = str(exc)
                query_error = str(exc)

        # Update query plan entry status
        if query_had_results:
            qp["provider_attempts"] = provider_attempts
            qp["status"] = "ok"
        elif query_error:
            qp["provider_attempts"] = provider_attempts
            qp["status"] = "failed"
        elif "skipped_no_symbol" in str(provider_attempts):
            qp["provider_attempts"] = provider_attempts
            qp["status"] = "skipped_no_symbol"
        else:
            qp["provider_attempts"] = provider_attempts
            qp["status"] = "empty"

        if not query_had_results and provider_attempts:
            coverage_gaps.append(query)

    # Cap total items
    all_items = all_items[:max_total_items]

    # Detect low-coverage topics
    topic_item_counts: dict[str, int] = {}
    for item in all_items:
        for tag in item.get("topic_tags", []):
            topic_item_counts[tag] = topic_item_counts.get(tag, 0) + 1

    low_coverage_topics = [t for t, c in topic_item_counts.items() if c < 2]

    # Detect stale news (all items older than lookback)
    stale_news = any(item.get("freshness_score", 1.0) < 0.2 for item in all_items) if all_items else False

    # Data quality
    has_partial_failure = any(ps.get("error") for ps in provider_status.values())

    data_quality: dict[str, Any] = {
        "news_snapshot_missing": not any_key_available and len(all_items) == 0,
        "provider_partial_failure": has_partial_failure,
        "stale_news": stale_news,
        "low_coverage_topics": low_coverage_topics,
    }

    return {
        "snapshot_type": "news_snapshot",
        "generated_at": now,
        "lookback_days": lookback_days,
        "provider_status": provider_status,
        "query_plan": query_plan,
        "items": all_items,
        "coverage_gaps": coverage_gaps,
        "data_quality": data_quality,
    }


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build news snapshot from KG context and available providers.")
    parser.add_argument(
        "--kg-context",
        required=True,
        type=Path,
        help="Path to knowledge_graph_context.private.json (required)",
    )
    parser.add_argument(
        "--portfolio-input",
        type=Path,
        default=None,
        help="Path to portfolio_input.private.json (optional fallback)",
    )
    parser.add_argument(
        "--provider-snapshot",
        type=Path,
        default=None,
        help="Path to provider_data_snapshot.private.json (optional)",
    )
    parser.add_argument(
        "--fund-profile-snapshot",
        type=Path,
        default=None,
        help="Path to fund_profile_snapshot.private.json (optional, for query enrichment)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path for news_snapshot.private.json",
    )

    args = parser.parse_args(argv)

    # Read required input
    kg_context = _read_json(args.kg_context)
    if kg_context is None:
        print(f"ERROR: Required file not found: {args.kg_context}", file=sys.stderr)
        return 1

    # Read optional inputs
    portfolio_input = _read_json(args.portfolio_input) if args.portfolio_input else None
    provider_snapshot = _read_json(args.provider_snapshot) if args.provider_snapshot else None
    # fund_profile_snapshot read for future query enrichment (passthrough)
    if args.fund_profile_snapshot:
        _read_json(args.fund_profile_snapshot)  # noqa: F841 — passthrough placeholder

    # Build snapshot
    result = build_news_snapshot(
        kg_context=kg_context,
        portfolio_input=portfolio_input,
        provider_snapshot=provider_snapshot,
    )

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"OK: news snapshot written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
