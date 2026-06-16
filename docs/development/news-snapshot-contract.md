# News Snapshot Contract

This document describes the news snapshot data structure and contract.

## Snapshot Structure

```json
{
  "snapshot_type": "news_snapshot",
  "generated_at": "2026-06-15T11:17:18.270393+00:00",
  "lookback_days": 30,
  "provider_status": {
    "tavily": {"available": true, "error": null},
    "bocha": {"available": true, "error": null},
    "serpapi": {"available": true, "error": null},
    "finnhub": {"available": true, "error": null}
  },
  "query_plan": [...],
  "items": [...],
  "coverage_gaps": [...],
  "data_quality": {...}
}
```

## Provider Status

Each provider has a status object:

- `available`: Boolean indicating if API key is set
- `error`: Error message if provider failed, or `null` if successful
- `status`: (optional) Special status like "skipped" for Finnhub when no symbol

### Provider-Specific Behavior

#### SerpAPI
- Continues working if API key is available
- Uses query_type and related_entities to improve relevance

#### Tavily
- Does NOT disable SSL verification by default
- Returns SSL error message if certificate verification fails
- Does not modify verification settings

#### Bocha
- Uses POST method by default
- Returns HTTP 405 error message if method not allowed
- Gracefully degrades on endpoint errors

#### Finnhub
- Requires a valid stock symbol
- Returns "skipped_no_symbol" status if no symbol is provided
- Does not treat missing symbol as an error

## Query Plan

Each query plan entry includes:

```json
{
  "query_id": "...",
  "query": "...",
  "query_type": "holding_company|benchmark|fund_profile|fund_manager|sector|macro|theme_fallback",
  "priority": 1,
  "entities": ["holding_company:NVIDIA", "fund:..."],
  "related_funds": ["基金名称"],
  "reason": "Top holding of ...",
  "source": "provider_snapshot|portfolio_input|derived|fallback",
  "confidence": "high|medium|low",
  "fallback": false,
  "provider_attempts": ["serpapi"],
  "status": "ok|failed|empty|skipped_no_symbol"
}
```

## News Items

Each news item includes:

```json
{
  "id": "...",
  "query_id": "...",
  "provider": "serpapi",
  "query": "NVIDIA 财报",
  "query_type": "holding_company",
  "priority": 1,
  "title": "NVIDIA Reports Record Revenue",
  "url": "https://...",
  "source": "Reuters",
  "published_at": "2026-06-15T10:00:00Z",
  "summary": "...",
  "language": "en",
  "related_entities": ["holding_company:NVIDIA"],
  "related_funds": ["华宝纳斯达克精选股票(QDII)A"],
  "topic_tags": ["纳斯达克", "半导体"],
  "reason": "Top holding of 华宝纳斯达克精选股票(QDII)A",
  "source_type": "provider_snapshot",
  "relevance_score": 0.85,
  "freshness_score": 0.9,
  "confidence": 0.8,
  "is_fallback_query": false
}
```

## Data Quality

```json
{
  "news_snapshot_missing": false,
  "provider_partial_failure": true,
  "stale_news": false,
  "low_coverage_topics": ["CPO"]
}
```

## Query Type Distribution

The news snapshot tracks query type distribution:

- `news_count_by_query_type`: Count of news items per query type
- `fallback_query_news_count`: Number of news from fallback queries
- `specific_query_news_count`: Number of news from specific queries

## Confidence Calculation

News item confidence is calculated as:

1. Base confidence from relevance and freshness scores
2. Multiplied by query confidence:
   - High query confidence: 1.2x (capped at 1.0)
   - Medium query confidence: 1.0x
   - Low query confidence: 0.8x

## Rules

1. **No API keys in output**: Provider API keys must not appear in snapshot
2. **Graceful degradation**: Provider failures should not block entire snapshot
3. **Query tracking**: Each news item must link back to its query plan entry
4. **Fallback marking**: Theme-level queries must be marked as fallback
5. **No duplication**: News items are deduplicated by URL and title+source+date