# KG-Driven Query Planning

This document describes the knowledge graph (KG) driven query planning system for fund-agent news and factor snapshots.

## Overview

The KG-driven query planning system generates news queries based on fund-level data rather than broad theme keywords. The priority order is:

1. **Fund look-through holdings** (highest priority)
   - Top holding companies
   - Top stocks/bonds
   - Top industries
   - Top regions
   - Top index constituents for index/QDII funds
   - Benchmark/index exposure
   - Fund manager / fund strategy facts

2. **Fund profile / product metadata**
   - Fund code
   - Fund name
   - Fund type
   - Benchmark
   - Tracking index
   - Investment scope
   - Fund manager
   - Manager strategy
   - Declared sector/theme

3. **Provider snapshot facts**
   - NAV / recent return windows
   - Drawdown
   - Volatility
   - Index/benchmark movement
   - Sector performance
   - Holding concentration
   - Risk bucket exposure

4. **Theme-level fallback queries** (lowest priority)
   - Broad queries like "QDII 海外 投资" or "短债 基金 收益"
   - Only used when look-through data is unavailable
   - Marked as `fallback: true` and `confidence: low`

## Entity Types

The KG supports the following entity types:

- `fund` - Fund identifier
- `fund_name` - Fund name
- `fund_code` - Fund code
- `fund_profile` - Fund profile metadata
- `fund_manager` - Fund manager
- `benchmark` - Benchmark/index name
- `index` - Index name
- `holding_company` - Top holding company
- `holding_ticker` - Holding ticker symbol
- `industry` - Industry/sector
- `region` - Geographic region
- `asset_class` - Asset class
- `risk_bucket` - Risk bucket (high/medium/low)
- `theme` - Theme tag
- `macro` - Macro topic

## Query Plan Structure

Each query plan entry includes:

```json
{
  "query_id": "...",
  "query": "...",
  "query_type": "holding_company|benchmark|fund_profile|fund_manager|sector|macro|theme_fallback",
  "priority": 1,
  "entities": [],
  "related_funds": [],
  "reason": "...",
  "source": "fund_profile_snapshot|provider_snapshot|portfolio_input|theme_fallback",
  "confidence": "high|medium|low",
  "fallback": false
}
```

## Priority Rules

- **Priority 1**: holding_company / holding_ticker / benchmark / tracking_index
- **Priority 2**: fund profile / fund manager / top industry / top region
- **Priority 3**: sector/theme queries derived from profile
- **Priority 4**: macro/risk queries
- **Priority 5**: theme_fallback (only when look-through data is unavailable)

## Data Sources

### Provider Snapshot

The system can consume fund profile and holdings data from `provider_data_snapshot.private.json`:

```json
{
  "fund_profiles": [
    {
      "fund_name": "...",
      "fund_type": "equity|bond|qdii|index|mixed|unknown",
      "benchmark": "...",
      "tracking_index": "...",
      "fund_manager": "...",
      "investment_scope": "...",
      "declared_theme_tags": []
    }
  ],
  "fund_holdings": [
    {
      "fund_name": "...",
      "holdings": [
        {
          "name": "...",
          "ticker": "...",
          "market": "CN|HK|US|unknown",
          "asset_type": "stock|bond|fund|cash|other|unknown",
          "weight": null,
          "sector": "...",
          "confidence": "high|medium|low",
          "source": "provider_snapshot|manual|unknown"
        }
      ]
    }
  ]
}
```

### KG Context Output

The `build_knowledge_graph_context.py` script produces:

```json
{
  "snapshot_type": "knowledge_graph_context",
  "entities": ["fund:...", "holding_company:...", "benchmark:..."],
  "entities_detail": [
    {
      "entity_id": "...",
      "entity_type": "...",
      "label": "...",
      "source": "portfolio_input|provider_snapshot|derived|fallback",
      "confidence": "high|medium|low",
      "related_funds": [],
      "data_quality_flags": []
    }
  ],
  "fund_entities": [...],
  "query_plan": [...],
  "missing_data": {...},
  "data_quality": {...}
}
```

## News Query Generation

The `build_news_snapshot.py` script uses the KG query plan to generate news queries. Each news item includes:

- `query_id` - Links back to the query plan
- `query_type` - Type of query (holding_company, benchmark, etc.)
- `priority` - Query priority
- `related_entities` - Entities from KG
- `related_funds` - Related funds
- `reason` - Why this query was generated
- `source_type` - Data source
- `is_fallback_query` - Whether this is a fallback query

## Factor Snapshot

The factor snapshot uses KG data to compute:

- **Data completeness factors**: holdings count, cost basis completeness, etc.
- **Profile coverage**: Whether fund profiles and holdings are available
- **News factors by query type**: Counts of news items by query_type

## Rules

1. **No guessing**: Do not guess holdings, fund codes, companies, NAV, units, or cost basis
2. **Graceful degradation**: If top holdings or fund profile data are not available, mark them missing
3. **Fallback marking**: Theme-level queries must be marked as `fallback: true`
4. **Confidence tracking**: Each entity and query has a confidence level
5. **No network calls**: KG context builder makes no network requests