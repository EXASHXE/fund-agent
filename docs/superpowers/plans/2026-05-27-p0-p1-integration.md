# P0-P1 Integration Plan: Wire New Modules + News APIs + Report Fix

## P0: Wire New Modules into CLI/Report Flow

### Task A: Add --use-agents flag + Workflow Branching

**Files to modify:**
1. `src/routes/cli_router.py` — Add `--use-agents` argument to `analyze` command (store_true, default False)
2. `src/core/workflow.py` — When `use_agents=True`:
   - Import and instantiate `KnowledgeGraphBuilder`
   - Build KG from fund holdings data: `graph = kg_builder.build_from_holdings(fund_data)`
   - Import and use `NewsPipeline` (new 8-stage) instead of `run_news_pipeline` (old keyword)
   - Import and use `ScoreEngine` (5-dimension) instead of `FundAnalyzer` (3-factor)
   - Map new data shapes to old report format as a bridge (adapter layer)
   - Fall back to old pipeline when `use_agents=False` (default, backward compatible)

**Data shape mapping needed:**
- Old `FundAnalyzer.score_fund()` → `{composite_score, macro_score, meso_score, micro_score, ...}`
- New `ScoreEngine.compute_composite()` → `CompositeScore(quant_score, fundamental_score, event_score, position_score, timing_score, ...)`
- Need adapter to map: quant→macro-like, fundamental→meso-like, etc. for old report renderer

### Task B: Fix Report `<details>` Nesting

**File:** `src/output/report.py` (lines ~196-197, ~543-544)

Change from:
```html
<details><summary>基金名</summary>
  ...
  <details><summary>新闻明细</summary>...</details>
</details>
```

To flat structure using Markdown headers or non-nested containers.

## P1: News APIs + Integration

### Task C: Finnhub US News Client

**New file:** `src/news/finnhub_client.py`
- `FinnhubNewsClient` class wrapping `finnhub-python`
- Methods: `get_company_news(symbol, from_date, to_date)`, `get_news_sentiment(symbol)`, `get_market_news(category)`
- Support US stock symbols from QDII holdings (AAPL, MSFT, NVDA, etc.)
- Error handling: free tier rate limited (60 calls/min), return empty on failures
- Config: API key from env var `FINNHUB_API_KEY`

### Task D: Tavily AI Search Client

**New file:** `src/news/tavily_client.py`
- `TavilySearchClient` class wrapping `tavily-python`
- Methods: `search_finance(query)`, `search_news(query, days=7)`
- Topic parameter: `topic="finance"` or `topic="news"`
- Error handling: free tier (1000 credits/mo), return empty on failures
- Config: API key from env var `TAVILY_API_KEY`

### Task E: Integrate into News Pipeline

**Modify:** `src/news/news_pipeline.py`
- Add `finnhub_client` and `tavily_client` as optional parameters to `NewsPipeline.__init__`
- In Stage 2 (targeted_retrieval): after AKShare stock news, also fetch Finnhub US news for QDII holdings
- In Stage 8 (event_extraction): optionally use Tavily to search for additional context
- All new sources are additive — AKShare remains primary for Chinese news

### Task F: Update requirements.txt
- Add `finnhub-python`
- Add `tavily-python`