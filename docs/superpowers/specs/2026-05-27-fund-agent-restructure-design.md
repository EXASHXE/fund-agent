# Fund-Agent Research-Grade Restructure Design

**Date**: 2026-05-27  
**Status**: Draft  
**Approach**: Incremental Module Replacement (Approach A)

## 1. Problem Statement

The current fund-agent is a **rule-based analysis tool with post-hoc AI adjustment**. Core problems:

1. **News relevance is terrible** — keyword search + title filtering yields ~95% noise, no holdings-driven linkage
2. **AI is a post-hoc modifier** — agents can only nudge scores ±10 on static rule-based baselines
3. **Scoring is static** — MacroScorer/MesoScorer are keyword→integer lookups with zero market data
4. **Recommendations are passive** — "持有观察" not "加仓10%" with evidence chain and trigger points
5. **No knowledge graph** — no relationship mapping between funds, holdings, industries, events
6. **No vector search** — no embedding-based similarity, reranking, or historical pattern matching

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     CLI + Streamlit UI                        │
│                   (preserved from current)                    │
├──────────────────────────────────────────────────────────────┤
│                  LangGraph Supervisor Agent                   │
│              (routing, orchestration, shared state)           │
│  ┌──────────┬───────────┬──────────┬──────────┬──────────┐  │
│  │News Agent│Research Ag│Quant Agt │Risk Agent │Strategy  │  │
│  │          │           │          │          │Agent     │  │
│  └────┬─────┴─────┬─────┴────┬─────┴────┬─────┴────┬─────┘  │
│       └───────────┴──────────┴─────────┴─────────┘         │
│                    Shared Tool Layer                          │
│  ┌────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ KG         │  │ Qdrant   │  │ AKShare  │  │ SQLite   │ │
│  │ (NetworkX) │  │ Vec DB   │  │ Fetcher  │  │ Storage  │ │
│  └────────────┘  └──────────┘  └──────────┘  └──────────┘ │
├──────────────────────────────────────────────────────────────┤
│              Preserved Engine Layer                           │
│  Config (Pydantic) │ Events │ Calculator │ Calendar │ Shared │
└──────────────────────────────────────────────────────────────┘
```

### Technology Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| LLM API | OpenAI-compatible (deepseek-v4-flash-free endpoint) | Preserves current pattern, easy provider switch |
| Vector DB | Qdrant | Python-native, hybrid search, lightweight self-host |
| Knowledge Graph | NetworkX in-memory | Single-user desktop tool, no infrastructure overhead |
| Agent Framework | LangGraph | Industry standard, built-in state/tool management |
| Data Source | AKShare (preserved) | Wide Chinese market data coverage |
| Storage | SQLite (preserved) + Qdrant | Existing pattern, no new infra |

### What's Preserved (Untouched)

- `src/cli.py`, `src/routes/` — CLI interface
- `src/config/` — Pydantic models, loader, defaults, shared
- `src/engine/` — Calendar, events, calculator
- `src/data/fetcher.py` — AKShare API wrappers
- `src/db/` — SQLAlchemy models, database, storage
- `src/output/templates.py` — Report template fragments
- Report contracts (`report_evidence.v2`, `agent_decisions.v2`) — Backward compatible

### What's Replaced

| Module | Current | New |
|--------|---------|-----|
| News | `src/news/` keyword search + sentiment | Holdings-driven KG+vector+AI pipeline |
| Scoring | `src/analysis/scoring/` keyword→int lookup | AI+factor hybrid with dynamic weights |
| Agents | `src/agents/` stub orchestrator | LangGraph multi-agent system |
| Recommend | `src/recommend/` momentum+diversity | Strategy engine with state machine |
| Context | `src/news/agent_context.py` JSON tasks | LangGraph shared state + tools |

### What's Added (New)

| Module | Purpose |
|--------|---------|
| `src/kg/` | Knowledge graph construction and query |
| `src/vectorstore/` | Qdrant integration and embedding pipeline |
| `src/agents/graphs/` | LangGraph agent definitions |
| `src/agents/tools/` | Tool definitions for agents |
| `src/strategy/` | Strategy engine with state machine |
| `src/events/` | Event extraction and taxonomy |

## 3. Knowledge Graph (NetworkX)

### 3.1 Node Types

```python
class KGNodeType(Enum):
    FUND = "fund"
    STOCK = "stock"
    INDUSTRY = "industry"      # SW industry classification
    THEME = "theme"            # Investment themes (AI, 新能源, 医药...)
    EVENT = "event"             # Market events (earnings, rate cuts, policy...)
    MACRO_FACTOR = "macro_factor"  # Interest rate, CPI, PMI...
```

### 3.2 Node Attributes

```python
# Fund node
{
    "code": "110011",
    "name": "易方达中小盘混合",
    "type": "hybrid",
    "style": "growth",          # growth / value / blend
    "size": "large",            # large / mid / small
    "manager": "张坤",
    "nav_date": "2026-05-27",
}

# Stock node
{
    "code": "600519",
    "name": "贵州茅台",
    "sector": "白酒",
    "industry": "食品饮料",
    "market_cap": "2.1T",
}

# Event node
{
    "id": "evt_20260527_rate_cut_us",
    "type": "rate_change",
    "subtype": "fed_rate_decision",
    "date": "2026-05-27",
    "polarity": -0.7,           # negative for funds
    "magnitude": 0.8,           # high impact
    "time_horizon": "medium",
    "description": "美联储维持利率不变，释放鹰派信号",
}
```

### 3.3 Edge Types

```python
class KGEdgeType(Enum):
    HOLDS = "holds"               # Fund → Stock (weight: float)
    BELONGS_TO = "belongs_to"     # Stock → Industry
    IN_THEME = "in_theme"         # Industry → Theme
    IMPACTS = "impacts"           # Event → Stock/Industry/Theme (polarity, magnitude)
    CORRELATES_WITH = "correlates"  # Theme → Theme (strength)
    EXPOSES = "exposes"           # Fund → MacroFactor (exposure_level)
```

### 3.4 Build Process

```python
class KnowledgeGraphBuilder:
    """Build KG from fund holdings data on startup, enrich from news."""
    
    def build_from_holdings(self, fund_data: dict) -> nx.DiGraph:
        """Phase 1: Build fund→stock→industry→theme from AKShare holdings."""
        ...
    
    def enrich_with_events(self, events: list[dict]) -> None:
        """Phase 2: Add event nodes and impact edges from news extraction."""
        ...
    
    def query_relevance(self, fund_code: str, news_item: dict) -> float:
        """Query KG for fund-news relevance score."""
        ...
    
    def get_impact_chain(self, event_id: str) -> list[dict]:
        """Trace event impact through KG to affected funds."""
        ...
    
    def get_fund_exposure(self, fund_code: str) -> dict:
        """Get fund's industry/theme/macro exposure profile."""
        ...
```

### 3.5 File Structure

```
src/kg/
├── __init__.py
├── graph.py          # KnowledgeGraphBuilder, query functions
├── schema.py         # Node/Edge type definitions, data classes
├── industry_map.py   # SW industry → theme mapping
└── enrichment.py     # Event enrichment, KG update from news
```

## 4. News System Restructure

### 4.1 Current vs New Pipeline

| Aspect | Current | New |
|--------|---------|-----|
| Retrieval | Keyword search + market scan | Holdings-driven targeted retrieval |
| Classification | Title keyword match | 6-layer weighted classification |
| Relevance | Simple term matching | Multi-factor relevance + KG overlap |
| Reranking | None | Vector similarity + AI rerank |
| Summary | Sentence extraction | Research-style analytical summary |
| Events | Flat 18-type pattern matching | Hierarchical event taxonomy + LLM extraction |

### 4.2 New Pipeline Stages

```
Stage 1: ENTITY EXTRACTION
  Fund → KG query → Top holdings (weighted) → Industries → Themes
  Output: SearchPlan{stocks, sectors, themes, events, macro_queries}

Stage 2: TARGETED RETRIEVAL
  For each heavy holding stock (weight ≥ 2%):
    AKShare stock_news_em(code) → stock-specific news
  For each sector/theme from KG:
    Market news with entity-driven queries
  Macro channel: separate collection, tagged differently
  Output: Raw news pool (per entity)

Stage 3: NEWS LAYER CLASSIFICATION
  Layer 1: Fund-direct (code/name match)         weight=1.0
  Layer 2: Heavy-holding stock (≥5% weight)       weight=0.8
  Layer 3: Industry/sector news                   weight=0.5
  Layer 4: Policy/macro news                      weight=0.3
  Layer 5: Overseas market news                   weight=0.2
  Layer 6: Black swan/risk events                 weight=variable
  Output: ClassifiedNewsList per fund per layer

Stage 4: RELEVANCE SCORING (replacing keyword match)
  relevance_score = 
    holding_overlap × 0.25 +    # KG: how many holdings are mentioned
    top10_hit × 0.20 +          # Is a top-10 holding mentioned?
    industry_hit × 0.15 +        # KG: related industry?
    theme_hit × 0.10 +           # KG: related theme?
    nav_correlation × 0.10 +     # Does news correlate with NAV movement?
    timeliness × 0.10 +         # Exponential decay from publication
    sentiment_severity × 0.10    # Polarity magnitude
  Output: ScoredNewsList per fund

Stage 5: VECTOR RERANKING
  Embed fund profile (holdings + style + industry vector)
  Embed each candidate news item
  combined_score = relevance × 0.6 + cosine_similarity × 0.4
  Keep top-K (default 20) per fund
  Output: RerankedNewsList per fund

Stage 6: AI RERANK (final pass)
  LLM ranks top-20 candidates with reasoning:
  - Fund impact assessment
  - Actionability evaluation
  - Risk level judgment
  Output: FinalRankedList with impact tags

Stage 7: RESEARCH-STYLE SUMMARY (per retained news item)
  For each news, LLM produces structured analysis:
  - what: 什么发生了
  - why_important: 为什么对这只基金重要
  - fund_impact: 对基金净值/持仓的影响
  - affected_holdings: 影响哪些重仓股
  - time_horizon: short/medium/long
  - risk_opportunity: risk flag or opportunity flag
  - suggested_action: 建议关注/操作
  Output: ResearchSummary list per fund

Stage 8: EVENT EXTRACTION
  LLM extracts structured events from retained news:
  {
    "type": "rate_change" | "earnings_surprise" | "policy_shift" | 
            "trade_restriction" | "commodity_price" | "geopolitical" |
            "industry_cycle" | "tech_breakthrough" | "black_swan" | "fund_flow",
    "subtype": str,
    "entities": [stock/industry codes],
    "polarity": -1.0 to 1.0,
    "magnitude": 0.0 to 1.0,
    "time_horizon": "short" | "medium" | "long",
    "description": str,
    "source_news_ids": [str],
  }
  Events → KG enrichment (IMPACTS edges)
```

### 4.3 Replacing Current Modules

| Current File | Status | Replacement |
|-------------|--------|-------------|
| `news_fetcher.py` | Replace | `src/news/retriever.py` (holdings-driven) |
| `sentiment.py` | Replace | `src/news/scorer.py` (multi-factor relevance) |
| `catalyst.py` | Replace | `src/news/scorer.py` + `src/events/extractor.py` |
| `pipeline.py` | Replace | `src/news/pipeline.py` (new pipeline) |
| `evaluator.py` | Keep (adapt) | `src/news/evaluator.py` (add quality metrics) |
| `entity_mapper.py` | Replace | KG query (src/kg/graph.py) |
| `agent_context.py` | Replace | LangGraph state + tools |
| `keyword_cache.py` | Replace | Qdrant + KG cache |
| `schemas.py` | Replace | New data models |

### 4.4 New File Structure

```
src/news/
├── __init__.py
├── pipeline.py       # RetrieverPipeline orchestrator
├── retriever.py      # Holdings-driven news retrieval
├── classifier.py     # 6-layer news classification
├── scorer.py         # Multi-factor relevance + vector reranking
├── summarizer.py     # Research-style AI summary
└── schemas.py        # Data models (SearchPlan, ScoredNews, etc.)

src/events/
├── __init__.py
├── extractor.py      # LLM event extraction
├── taxonomy.py       # Event type hierarchy
└── enrichment.py     # KG update from events
```

## 5. AI Scoring System

### 5.1 Current vs New Scoring

| Aspect | Current | New |
|--------|---------|-----|
| Macro | Keyword→int lookup (8+5+8=20) | Dynamic quant + AI macro assessment |
| Meso | Keyword→int lookup (8+8+8+8=30) | AI fundamental analysis |
| Micro | Partially data-driven | Full quant metrics + position analysis |
| Weights | Fixed 20/30/50 | Dynamic regime-based |
| Agent role | Post-hoc ±10 adjustment | Core scoring authority |
| Event impact | 5% weight in meso factor | Dedicated EventScore dimension |

### 5.2 New Score Composition

```
FundScore = QuantScore(ω_q) + FundamentalScore(ω_f) + EventScore(ω_e)
          + PositionScore(ω_p) + TimingScore(ω_t)

Default weights (normal market):
  ω_q=0.40, ω_f=0.20, ω_e=0.15, ω_p=0.15, ω_t=0.10

High volatility regime:
  ω_q=0.25, ω_f=0.15, ω_e=0.30, ω_p=0.20, ω_t=0.10

Trending market regime:
  ω_q=0.35, ω_f=0.25, ω_e=0.10, ω_p=0.15, ω_t=0.15

Regime detection: LLM-assisted based on recent volatility + event density + market trend
```

### 5.3 Sub-Score Definitions

#### 5.3.1 QuantScore (preserved, enhanced)

Keep all existing metrics from `metrics.py`:
- Sharpe ratio, Sortino ratio, Jensen Alpha, Beta, IR, Calmar ratio
- Max drawdown, annual volatility, win rate, HHI concentration

**Enhancement**: Dynamic weight based on data completeness and regime.

```python
class QuantScore:
    """Data-driven quantitative scoring. No keyword lookups."""
    
    def compute(self, fund_data: dict, regime: MarketRegime) -> ScoreComponent:
        metrics = MetricsCalculator().compute_all(fund_data)
        weights = self._regime_weights(regime)
        raw_score = sum(metrics[key] * weights[key] for key in weights)
        return ScoreComponent(
            score=normalize(raw_score, 0, 100),
            detail=metrics,
            weights=weights,
            confidence=data_completeness_confidence(fund_data),
        )
```

#### 5.3.2 FundamentalScore (NEW - AI-driven)

```python
class FundamentalScore:
    """AI assessment of fundamental environment."""
    
    def compute(self, fund_data: dict, kg: KnowledgeGraph, 
                events: list[Event]) -> ScoreComponent:
        # KG queries for industry/theme context
        exposure = kg.get_fund_exposure(fund_data["code"])
        recent_events = kg.get_recent_events(fund_data["code"])
        
        # LLM assessment
        assessment = llm_assess(
            prompt=FUNDAMENTAL_PROMPT,
            context={
                "fund": fund_data,
                "industry_exposure": exposure,
                "recent_events": recent_events,
                "nav_trend": fund_data["nav_series"][-60:],
            }
        )
        return ScoreComponent(
            score=assessment.score,        # 0-100
            detail=assessment.breakdown,    # {industry, policy, cycle, macro, risk}
            confidence=assessment.confidence,
        )
```

Sub-factors assessed by LLM:
- **Industry prosperity** (行业景气度): Based on KG industry data + recent event polarity
- **Policy environment** (政策环境): From event extraction policy signals
- **Industry cycle position** (产业周期): From KG industry theme + LLM judgment
- **Macro environment** (宏观环境): From macro factor edges in KG
- **Risk environment** (风险环境): From event magnitude + NAV volatility

#### 5.3.3 EventScore (NEW - from news pipeline)

```python
class EventScore:
    """Score driven by news events extracted from holdings-driven pipeline."""
    
    def compute(self, fund_code: str, events: list[Event],
                kg: KnowledgeGraph) -> ScoreComponent:
        fund_impact_events = kg.get_impact_chain_for_fund(fund_code)
        
        weighted_score = 0
        for event in fund_impact_events:
            path_impact = kg.calculate_impact_magnitude(fund_code, event)
            time_weight = exponential_decay(event.date, lambda=0.2)
            weighted_score += event.polarity * event.magnitude * path_impact * time_weight
        
        return ScoreComponent(
            score=normalize(weighted_score, 0, 100),
            detail={"bullish_events": [...], "bearish_events": [...], 
                    "black_swan": bool, "event_count": N},
            confidence=event_coverage_confidence(fund_code, events),
        )
```

#### 5.3.4 PositionScore (NEW - enhanced holdings analysis)

```python
class PositionScore:
    """Analyze portfolio structure risk."""
    
    def compute(self, fund_data: dict, kg: KnowledgeGraph) -> ScoreComponent:
        holdings = fund_data["holdings"]
        concentration_risk = compute_hhi(holdings)                    # existing
        style_drift = detect_style_drift(fund_data, kg)              # NEW
        industry_exposure = kg.get_industry_concentration(fund_data)  # NEW
        single_name_risk = max(h["weight"] for h in holdings)        # existing
        overseas = compute_overseas_exposure(fund_data)               # existing
        
        return ScoreComponent(
            score=normalize(concentration_risk * 0.25 + 
                           (1 - style_drift) * 0.25 +
                           (1 - industry_exposure) * 0.25 + 
                           (1 - single_name_risk) * 0.15 +
                           (1 - overseas) * 0.10, 0, 100),
            detail={...},
            confidence=holdings_completeness(fund_data),
        )
```

#### 5.3.5 TimingScore (NEW - AI judgment)

```python
class TimingScore:
    """AI judgment on timing suitability."""
    
    def compute(self, fund_data: dict, regime: MarketRegime,
                events: list[Event]) -> ScoreComponent:
        assessment = llm_assess(
            prompt=TIMING_PROMPT,
            context={
                "fund": fund_data,
                "regime": regime,
                "recent_events": events[:5],
                "nav_trend": fund_data["nav_series"][-20:],
                "current_valuation": fund_data.get("pe_ratio"),
            }
        )
        return ScoreComponent(
            score=assessment.score,
            detail={
                "dca_suitability": assessment.dca_suitability,
                "lump_sum_suitability": assessment.lump_sum_suitability,
                "watch_signal": assessment.watch_signal,
                "risk_flag": assessment.risk_flag,
            },
            confidence=assessment.confidence,
        )
```

### 5.4 Market Regime Detection

```python
class MarketRegime(Enum):
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    TRENDING = "trending"
    CRISIS = "crisis"

def detect_regime(nav_series, events, vol_window=20) -> MarketRegime:
    """Detect current market regime from NAV volatility and event density."""
    recent_vol = compute_rolling_volatility(nav_series, window=vol_window)
    event_density = count_high_magnitude_events(events, days=7)
    
    if recent_vol > 2.0 * historical_avg_vol or event_density > 3:
        return MarketRegime.HIGH_VOLATILITY
    elif recent_vol < 0.5 * historical_avg_vol and has_trend(nav_series, window=60):
        return MarketRegime.TRENDING
    elif event_density > 5 or has_black_swan(events):
        return MarketRegime.CRISIS
    else:
        return MarketRegime.NORMAL
```

### 5.5 Replacing Current Modules

| Current File | Status | Replacement |
|-------------|--------|-------------|
| `scoring/macro.py` | Delete | `src/analysis/scoring/quant.py` |
| `scoring/meso.py` | Delete | `src/analysis/scoring/fundamental.py` (AI) |
| `scoring/micro.py` | Refactor | `src/analysis/scoring/quant.py` (data-driven parts kept) |
| `scorer.py` | Refactor | `src/analysis/scoring/engine.py` (new composition) |
| `factors.py` | Enhance | `src/analysis/scoring/factors.py` (dynamic weights) |

### 5.6 New File Structure

```
src/analysis/scoring/
├── __init__.py
├── engine.py         # ScoreEngine orchestrator with regime detection
├── quant.py          # QuantScore (data-driven, dynamic weights)
├── fundamental.py    # FundamentalScore (AI + KG-driven)
├── event.py          # EventScore (from news pipeline + KG)
├── position.py       # PositionScore (enhanced holdings analysis)
├── timing.py         # TimingScore (AI judgment)
├── regime.py         # MarketRegime detection
├── factors.py        # Factor matrix (enhanced, dynamic weights)
└── types.py          # ScoreComponent, MarketRegime, etc.
```

## 6. Strategy Engine

### 6.1 Current vs New

| Aspect | Current | New |
|--------|---------|-----|
| Output | Static text ("持有观察") | Structured StrategyAdvice with state machine |
| Actions | 4 levels (buy/hold/reduce/sell) | 6 actions (hold/add/reduce/switch/wait/stop_loss) |
| Evidence | None | Full evidence chain from KG + scores + events |
| Triggers | None | Observation points and state transitions |
| Stop logic | Volatility-based formula | Multi-factor + regime-aware |
| Timing | None | DCA suitability, lump-sum assessment, watch signals |

### 6.2 StrategyAdvice Schema

```python
class StrategyAction(Enum):
    HOLD = "hold"
    ADD = "add"
    REDUCE = "reduce"
    SWITCH = "switch"
    WAIT = "wait"
    STOP_LOSS = "stop_loss"

@dataclass
class StrategyAdvice:
    action: StrategyAction
    confidence: float                     # 0.0-1.0
    risk_level: Literal["low", "medium", "high", "extreme"]
    reasons: list[str]                    # Evidence chain
    evidence: list[str]                   # KG node IDs + event IDs
    trigger_events: list[str]             # What to watch for state change
    position_suggestion: str             # "加仓10%", "减仓至3%", etc.
    time_horizon: Literal["short", "medium", "long"]
    stop_loss_pct: float | None          # Regime-aware stop loss
    take_profit_pct: float | None        # Regime-aware take profit
    next_observation_points: list[str]    # Time-based or event-based triggers
    state: StrategyState                 # Current state in state machine
    valid_transitions: dict              # State → [possible next states]
```

### 6.3 Strategy State Machine

```
         ┌──────┐  event_bullish  ┌──────┐  trend_confirmed  ┌──────┐
         │ WAIT │───────────────→│ HOLD │──────────────────→│  ADD │
         └──┬───┘                └──┬───┘                    └──┬───┘
            │                       │ risk_signal               │ profit_target
            │                       ↓                            ↓
            │                 ┌────────┐                 ┌───────────┐
            │                 │REDUCE  │                 │TAKE_PROFIT│
            │                 └───┬────┘                 └───────────┘
            │                     │ risk_escalation
            │                     ↓
            │               ┌─────────┐
            │               │STOP_LOSS│
            │               └─────────┘
            │                     
            └─── re-evaluate ─────┘ (conditions not met)

State transition triggers:
  WAIT → HOLD:  favorable event + confirming trend
  WAIT → WAIT:  insufficient evidence (re-evaluate next cycle)
  HOLD → ADD:   trend confirmation + low risk
  HOLD → REDUCE: risk signal (event or quant deterioration)
  ADD → TAKE_PROFIT: target profit reached
  REDUCE → STOP_LOSS: accelerating risk / black swan
  Any → WAIT: regime change / insufficient data
```

### 6.4 File Structure

```
src/strategy/
├── __init__.py
├── engine.py         # StrategyEngine main class
├── state_machine.py  # StrategyState transitions
├── advisor.py        # StrategyAdvice generation (AI + rules)
├── stop_logic.py     # Regime-aware stop-loss/take-profit
└── schemas.py        # StrategyAction, StrategyAdvice, StrategyState
```

## 7. Multi-Agent System (LangGraph)

### 7.1 Agent Architecture

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated

# Shared state across all agents
class FundResearchState(TypedDict):
    # Input
    portfolio_config: dict
    report_date: str
    
    # Data layer (populated by tools)
    funds_data: dict              # Per-fund raw data
    knowledge_graph: dict         # KG adjacency snapshot (serializable dict, not nx.Graph)
                                   # Keys: {nodes: [...], edges: [...], exposures: {fund_code: {...}}}
    
    # News pipeline results
    search_plans: dict            # Per-fund SearchPlan
    raw_news: dict                # Per-fund raw news pool
    classified_news: dict         # Per-fund classified news
    scored_news: dict             # Per-fund scored+reranked news
    research_summaries: dict      # Per-fund research-style summaries
    extracted_events: dict        # Per-fund extracted events
    
    # Scoring results
    market_regime: str            # Detected regime
    quant_scores: dict            # Per-fund QuantScore
    fundamental_scores: dict      # Per-fund FundamentalScore
    event_scores: dict            # Per-fund EventScore
    position_scores: dict         # Per-fund PositionScore
    timing_scores: dict           # Per-fund TimingScore
    final_scores: dict            # Per-fund composite scores
    
    # Strategy results
    risk_assessments: dict        # Per-fund risk assessment
    strategies: dict              # Per-fund StrategyAdvice
    portfolio_strategy: dict      # Portfolio-level strategy
    
    # Orchestration
    iteration: int
    next_agent: str
    errors: list[str]
```

### 7.2 Supervisor Agent

```python
# Supervisor routing logic
SUPERVISOR_PROMPT = """You are a fund research supervisor. Route tasks to specialized agents:
- NEWS: When news collection, event extraction, or market sentiment is needed
- RESEARCH: When fundamental analysis, industry assessment, or KG reasoning is needed
- QUANT: When quantitative scoring, metrics computation, or risk analysis is needed
- RISK: When concentration, style drift, or black swan risk assessment is needed
- STRATEGY: When strategy synthesis, action recommendation, or timing judgment is needed

Always run NEWS first (data collection), then QUANT and RISK in parallel,
then RESEARCH (needs scores + events), finally STRATEGY (needs all results)."""
```

### 7.3 Individual Agents

#### NewsAgent
- **Tools**: `search_news`, `rerank_news`, `extract_events`, `query_kg`, `embed_query`, `search_similar_events`
- **Input**: Fund codes, KG snapshot
- **Output**: Per-fund news, events, summaries

#### ResearchAgent (Fundamental)
- **Tools**: `query_kg`, `analyze_holdings`, `assess_industry`, `check_policy_signal`
- **Input**: Fund data, KG, events, quant scores
- **Output**: Per-fund FundamentalScore, industry assessment

#### QuantAgent
- **Tools**: `compute_metrics`, `analyze_positions`, `compute_correlations`, `stress_test`
- **Input**: Fund data
- **Output**: Per-fund QuantScore, feature matrix, correlations

#### RiskAgent
- **Tools**: `analyze_concentration`, `check_style_drift`, `assess_black_swan`, `compute_var`
- **Input**: Fund data, KG, events
- **Output**: Per-fund risk assessment, PositionScore

#### StrategyAgent
- **Tools**: `query_all_scores`, `query_kg_events`, `assess_timing`, `generate_strategy`
- **Input**: All scores, events, KG
- **Output**: Per-fund StrategyAdvice, portfolio strategy

### 7.4 Tool Definitions

```python
# Each tool has strict input/output schema
tools = {
    # Data tools
    "search_news": Tool(fn=search_news_handler, description="..."),
    "rerank_news": Tool(fn=rerank_news_handler, description="..."),
    
    # KG tools
    "query_kg": Tool(fn=kg_query_handler, description="..."),
    "get_fund_exposure": Tool(fn=kg_exposure_handler, description="..."),
    "get_impact_chain": Tool(fn=kg_impact_handler, description="..."),
    
    # Vector tools
    "embed_query": Tool(fn=embed_handler, description="..."),
    "search_similar_events": Tool(fn=vector_search_handler, description="..."),
    
    # Analysis tools
    "compute_metrics": Tool(fn=metrics_handler, description="..."),
    "analyze_positions": Tool(fn=position_handler, description="..."),
    
    # Strategy tools
    "assess_timing": Tool(fn=timing_handler, description="..."),
    "generate_strategy": Tool(fn=strategy_handler, description="..."),
}
```

### 7.5 File Structure

```
src/agents/
├── __init__.py
├── graph.py            # LangGraph StateGraph definition
├── state.py            # FundResearchState definition
├── supervisor.py       # Supervisor routing logic
├── graphs/
│   ├── __init__.py
│   ├── news_agent.py       # NewsAgent node
│   ├── research_agent.py   # ResearchAgent node
│   ├── quant_agent.py      # QuantAgent node
│   ├── risk_agent.py       # RiskAgent node
│   └── strategy_agent.py   # StrategyAgent node
├── tools/
│   ├── __init__.py
│   ├── kg_tools.py          # KG query, exposure, impact chain
│   ├── vector_tools.py       # Embed, search similar
│   ├── news_tools.py         # Search, rerank, extract events
│   ├── analysis_tools.py    # Metrics, positions, correlations
│   └── strategy_tools.py    # Timing, strategy generation
└── prompts/
    ├── __init__.py
    ├── supervisor.md
    ├── news_agent.md
    ├── research_agent.md
    ├── quant_agent.md
    ├── risk_agent.md
    └── strategy_agent.md
```

## 8. Vector Store (Qdrant)

### 8.1 Collections

| Collection | Content | Embedding | Metadata |
|-----------|---------|-----------|----------|
| `fund_news` | News items | Text embedding | fund_code, date, layer, source, entities, relevance_score |
| `fund_events` | Extracted events | Event description embedding | event_type, polarity, magnitude, affected_entities |
| `fund_styles` | Fund style profiles | Profile text embedding | fund_code, style, industry, size |
| `fund_reports` | Historical reports | Report chunk embedding | fund_code, date, score_level |

### 8.2 Embedding Pipeline

```python
class EmbeddingPipeline:
    """Embed text → upsert to Qdrant with metadata."""
    
    def __init__(self, qdrant_client, embedding_model, collection: str):
        self.client = qdrant_client
        self.model = embedding_model  # OpenAI-compatible embedding API
        self.collection = collection
    
    def embed_and_store(self, items: list[dict], text_field: str = "content"):
        for item in items:
            vector = self.model.embed(item[text_field])
            self.client.upsert(
                collection_name=self.collection,
                points=[{
                    "id": item["id"],
                    "vector": vector,
                    "payload": {k: v for k, v in item.items() if k != text_field},
                }]
            )
    
    def search(self, query: str, filters: dict = None, limit: int = 10):
        query_vector = self.model.embed(query)
        return self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=filters,
            limit=limit,
        )
```

### 8.3 Fundalike Search

```python
def find_similar_funds(fund_code: str, top_k: int = 5) -> list[dict]:
    """Find funds with similar style/exposure profile."""
    profile = kg.get_fund_exposure(fund_code)
    profile_text = format_profile_for_embedding(profile)
    results = vector_store.search(
        collection="fund_styles",
        query=profile_text,
        filters={"fund_code": {"ne": fund_code}},
        limit=top_k,
    )
    return results
```

### 8.4 File Structure

```
src/vectorstore/
├── __init__.py
├── client.py          # QdrantClient wrapper, collection management
├── embedding.py       # OpenAI-compatible embedding pipeline
├── collections.py     # Collection definitions, schema
└── search.py          # Search utilities (fundalike, similar events, etc.)
```

## 9. Data Flow: End-to-End

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CONFIG LOAD (preserved)                                      │
│    fund-portfolio.yaml → PortfolioConfig → KG build trigger      │
├─────────────────────────────────────────────────────────────────┤
│ 2. DATA ACQUISITION (preserved)                                  │
│    AKShare fetchers → fund_data dict (basic/perf/nav/holdings)  │
│    KG enrichment: holdings → stock → industry → theme edges     │
├─────────────────────────────────────────────────────────────────┤
│ 3. NEWS PIPELINE (NEW)                                           │
│    Supervisor → NewsAgent                                        │
│    ├── KG query → SearchPlan per fund                            │
│    ├── Targeted retrieval per entity                             │
│    ├── 6-layer classification                                     │
│    ├── Multi-factor relevance scoring (KG overlay)               │
│    ├── Vector reranking (Qdrant)                                  │
│    ├── AI reranking (LLM top-20)                                 │
│    ├── Research-style summaries (LLM)                             │
│    └── Event extraction → KG enrichment                          │
├─────────────────────────────────────────────────────────────────┤
│ 4. SCORING (NEW)                                                 │
│    Supervisor → QuantAgent ‖ RiskAgent (parallel)                │
│    ├── Regime detection                                           │
│    ├── QuantScore (data-driven, dynamic weights)                 │
│    ├── PositionScore (KG-enhanced holdings)                      │
│    ├── EventScore (from news pipeline)                           │
│    ├── ResearchAgent → FundamentalScore (AI + KG)                │
│    ├── ResearchAgent → TimingScore (AI judgment)                  │
│    ├── Dynamic weight composition per regime                     │
│    └── Final composite score per fund                             │
├─────────────────────────────────────────────────────────────────┤
│ 5. STRATEGY (NEW)                                                │
│    StrategyAgent                                                  │
│    ├── Input: all scores + events + KG exposure                  │
│    ├── Strategy state machine per fund                            │
│    ├── Evidence chain from KG nodes                               │
│    ├── Regime-aware stop-loss/take-profit                         │
│    └── Structured StrategyAdvice per fund                         │
├─────────────────────────────────────────────────────────────────┤
│ 6. PORTFOLIO SYNTHESIS (enhanced)                                │
│    StrategyAgent                                                  │
│    ├── Portfolio-level stance assessment                          │
│    ├── Cross-fund risk aggregation (KG impact propagation)       │
│    └── Portfolio StrategyAdvice with rebalancing hints            │
├─────────────────────────────────────────────────────────────────┤
│ 7. EVIDENCE + REPORT (enhanced)                                  │
│    Build report_evidence.v3 with new fields                      │
│    Generate report.md with strategy sections                      │
│    Validate final report                                          │
└─────────────────────────────────────────────────────────────────┘
```

## 10. Report Contract Changes

### 10.1 Evidence Contract Evolution (v2 → v3)

The `report_evidence.v2` contract is preserved and extended:

```json
{
  "schema_version": "report_evidence.v3",
  "...existing_v2_fields...": "...",
  
  "kg_snapshot": {
    "fund_exposure": {"CODE": {"industries": [], "themes": [], "macro_factors": []}},
    "impact_chains": {"event_id": {"affected_funds": [], "paths": []}}
  },
  
  "news_evidence": {
    "CODE": {
      "...existing_fields...": "...",
      "classified_news": {"layer_1": [], "layer_2": [], ...},
      "research_summaries": [{"what": "", "why_important": "", "fund_impact": "", ...}],
      "extracted_events": [{"type": "", "polarity": 0.0, "magnitude": 0.0, ...}]
    }
  },
  
  "score_evidence": {
    "CODE": {
      "regime": "normal",
      "quant_score": {"score": 0, "detail": {}, "confidence": 0.0},
      "fundamental_score": {"score": 0, "detail": {}, "confidence": 0.0},
      "event_score": {"score": 0, "detail": {}, "confidence": 0.0},
      "position_score": {"score": 0, "detail": {}, "confidence": 0.0},
      "timing_score": {"score": 0, "detail": {}, "confidence": 0.0},
      "weights_used": {"quant": 0.4, "fundamental": 0.2, ...},
      "composite_score": 0,
      "score_level": "green|yellow|orange|red"
    }
  },
  
  "strategy_evidence": {
    "CODE": {
      "action": "hold|add|reduce|switch|wait|stop_loss",
      "confidence": 0.0,
      "risk_level": "low|medium|high|extreme",
      "reasons": [],
      "evidence": [],
      "trigger_events": [],
      "position_suggestion": "",
      "time_horizon": "short|medium|long",
      "stop_loss_pct": null,
      "take_profit_pct": null,
      "next_observation_points": [],
      "state": "hold"
    }
  }
}
```

### 10.2 Agent Decisions Contract (v3)

```json
{
  "schema_version": "agent_decisions.v3",
  "...existing_v2_fields...": "...",
  
  "fund_strategies": {
    "CODE": {
      "action": "hold",
      "confidence": 0.82,
      "risk_level": "medium",
      "reasons": ["行业景气度下降", "重仓股财报低于预期"],
      "evidence": ["stock:600519", "event:earnings_miss_Q1"],
      "trigger_events": ["下月央行LPR决议", "白酒行业PMI数据"],
      "position_suggestion": "维持当前仓位",
      "time_horizon": "medium",
      "stop_loss_pct": 18.5,
      "take_profit_pct": 35.0,
      "next_observation_points": ["2026-06-15 季度报告", "2026-07 FOMC会议"],
      "state": "hold"
    }
  }
}
```

### 10.3 Backward Compatibility

- `report_evidence.v2` remains parseable — v3 adds new top-level keys, doesn't remove existing ones
- `agent_decisions.v2` remains parseable — v3 adds `fund_strategies`, keeps `fund_scores`
- Existing CLI commands preserved: `analyze`, `score`, `news`, `recommend`, `snapshot`, `ui`
- New command: `analyze --use-agents` to activate LangGraph pipeline (falls back to rule-based if unavailable)

## 11. Directory Structure (Complete)

```
src/
├── __init__.py
├── cli.py                    # Preserved (enhanced with --use-agents flag)
├── config/                   # Preserved
│   ├── schema.py
│   ├── loader.py
│   ├── defaults.py           # Enhanced: dynamic weight configs
│   └── shared.py
├── core/                     # Preserved + enhanced
│   ├── contracts.py          # Enhanced: v3 schemas
│   └── workflow.py           # Enhanced: agent pipeline integration
├── engine/                   # Preserved
│   ├── calendar.py
│   ├── events.py
│   └── calculator.py
├── data/                     # Preserved
│   └── fetcher.py
├── db/                       # Preserved
│   ├── models.py
│   ├── database.py
│   └── storage.py
├── kg/                       # NEW
│   ├── __init__.py
│   ├── graph.py              # KnowledgeGraphBuilder
│   ├── schema.py             # Node/Edge types
│   ├── industry_map.py       # SW industry → theme mapping
│   └── enrichment.py         # Event enrichment, KG update
├── vectorstore/              # NEW
│   ├── __init__.py
│   ├── client.py             # Qdrant client wrapper
│   ├── embedding.py          # Embedding pipeline
│   ├── collections.py        # Collection schemas
│   └── search.py             # Search utilities
├── events/                   # NEW
│   ├── __init__.py
│   ├── extractor.py          # LLM event extraction
│   ├── taxonomy.py           # Event type hierarchy
│   └── enrichment.py         # KG update from events
├── news/                     # REPLACED
│   ├── __init__.py
│   ├── pipeline.py            # New RetrieverPipeline
│   ├── retriever.py           # Holdings-driven retrieval
│   ├── classifier.py          # 6-layer classification
│   ├── scorer.py              # Multi-factor relevance + vector reranking
│   ├── summarizer.py          # Research-style AI summary
│   └── schemas.py              # New data models
├── analysis/                 # RESTRUCTURED
│   ├── __init__.py
│   ├── scorer.py              # Preserved (orchestration adapted)
│   ├── scoring/               # NEW structure
│   │   ├── __init__.py
│   │   ├── engine.py          # ScoreEngine with regime detection
│   │   ├── quant.py           # QuantScore (data-driven)
│   │   ├── fundamental.py     # FundamentalScore (AI + KG)
│   │   ├── event.py           # EventScore (from news + KG)
│   │   ├── position.py        # PositionScore (enhanced holdings)
│   │   ├── timing.py          # TimingScore (AI judgment)
│   │   ├── regime.py          # MarketRegime detection
│   │   ├── factors.py         # Enhanced factor matrix
│   │   └── types.py           # Shared types
│   ├── metrics.py             # Preserved
│   ├── holdings.py            # Preserved (enhanced)
│   ├── correlation.py         # Preserved
│   ├── stress.py              # Preserved (enhanced with KV impact)
│   ├── portfolio_risk.py      # Preserved (enhanced)
│   └── loader.py              # Preserved
├── strategy/                 # NEW
│   ├── __init__.py
│   ├── engine.py              # StrategyEngine
│   ├── state_machine.py       # StrategyState transitions
│   ├── advisor.py             # StrategyAdvice generation
│   ├── stop_logic.py          # Regime-aware stop-loss/take-profit
│   └── schemas.py             # StrategyAction, StrategyState, StrategyAdvice
├── agents/                   # REPLACED
│   ├── __init__.py
│   ├── graph.py               # LangGraph StateGraph definition
│   ├── state.py               # FundResearchState
│   ├── supervisor.py          # Supervisor routing logic
│   ├── graphs/
│   │   ├── __init__.py
│   │   ├── news_agent.py
│   │   ├── research_agent.py
│   │   ├── quant_agent.py
│   │   ├── risk_agent.py
│   │   └── strategy_agent.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── kg_tools.py
│   │   ├── vector_tools.py
│   │   ├── news_tools.py
│   │   ├── analysis_tools.py
│   │   └── strategy_tools.py
│   └── prompts/
│       ├── __init__.py
│       ├── supervisor.md
│       ├── news_agent.md
│       ├── research_agent.md
│       ├── quant_agent.md
│       ├── risk_agent.md
│       └── strategy_agent.md
├── forecast/                 # Enhanced
│   └── engine.py             # Enhanced: KG-aware trend matrix
├── recommend/                # Preserved (strategy replaces primary function)
│   └── engine.py             # Kept as fallback, supplemented by strategy
├── output/                   # Enhanced
│   ├── report.py             # Enhanced: strategy sections
│   ├── templates.py          # Preserved
│   └── validator.py          # Enhanced: v3 validation
├── services/                 # Enhanced
│   ├── scoring_service.py
│   ├── report_service.py
│   ├── portfolio_service.py
│   ├── snapshot_service.py
│   ├── news_service.py
│   └── workflow_context.py
├── routes/                   # Preserved (enhanced with new flags)
│   ├── cli_router.py
│   └── commands.py
└── ui/                       # Preserved
    └── app.py
```

## 12. Phased Implementation Plan

### Phase 1: Infrastructure (Week 1-2)

**Goal**: Build KG, Qdrant, and LangGraph skeleton without touching existing code.

| Task | Files | Verification |
|------|-------|-------------|
| KG module | `src/kg/*.py` | Unit tests: build graph from test holdings, query relevance, trace impact |
| Qdrant module | `src/vectorstore/*.py` | Unit tests: embed, upsert, search with test data |
| Event taxonomy | `src/events/taxonomy.py` | Unit tests: classify known event types |
| LangGraph skeleton | `src/agents/state.py`, `src/agents/graph.py` | Integration test: empty graph runs without error |
| Score types | `src/analysis/scoring/types.py` | Unit tests: ScoreComponent creation, MarketRegime enum |

**Key constraint**: No changes to existing working code. All new modules are additive.

### Phase 2: News System (Week 3-4)

**Goal**: Replace keyword search with holdings-driven pipeline.

| Task | Files | Verification |
|------|-------|-------------|
| Retriever | `src/news/retriever.py` | Integration test: fetch news for test fund via holdings path |
| Classifier | `src/news/classifier.py` | Unit test: classify news into 6 layers |
| Scorer | `src/news/scorer.py` | Unit test: relevance scoring matches KG weights |
| Summarizer | `src/news/summarizer.py` | Manual test: research-style summary quality |
| Event extractor | `src/events/extractor.py` | Unit test: extract structured events from test news |
| Pipeline orchestration | `src/news/pipeline.py` | Integration test: end-to-end news pipeline |
| `--use-agents` CLI flag | `src/routes/commands.py` | CLI test: `python -m src.cli analyze --use-agents` |

**Key constraint**: Old pipeline remains as fallback (`--no-agents`). New pipeline activated by `--use-agents`.

### Phase 3: Scoring System (Week 5-6)

**Goal**: Replace keyword-based scoring with AI+factor hybrid.

| Task | Files | Verification |
|------|-------|-------------|
| QuantScore refactor | `src/analysis/scoring/quant.py` | Unit test: same metrics, dynamic weights |
| FundamentalScore | `src/analysis/scoring/fundamental.py` | Integration test: LLM produces score + rationale |
| EventScore | `src/analysis/scoring/event.py` | Unit test: KG-driven event scoring |
| PositionScore | `src/analysis/scoring/position.py` | Unit test: enhanced holdings analysis |
| TimingScore | `src/analysis/scoring/timing.py` | Integration test: LLM timing assessment |
| Regime detection | `src/analysis/scoring/regime.py` | Unit test: detect market regimes |
| ScoreEngine | `src/analysis/scoring/engine.py` | Integration test: composite scores with dynamic weights |
| Report rendering | `src/output/report.py` | Visual test: new score sections in report |

**Key constraint**: Report evidence v3 is backward-compatible. Old CLI commands still work.

### Phase 4: Strategy + Agents (Week 7-8)

**Goal**: Full multi-agent system with strategy engine.

| Task | Files | Verification |
|------|-------|-------------|
| Strategy engine | `src/strategy/*.py` | Unit test: state transitions, advice generation |
| LangGraph agents | `src/agents/graphs/*.py` | Integration test: each agent produces valid output |
| Agent tools | `src/agents/tools/*.py` | Unit tests per tool |
| Agent prompts | `src/agents/prompts/*.md` | Manual test: agent response quality |
| Supervisor | `src/agents/supervisor.py` | Integration test: full pipeline routing |
| Full pipeline | `src/agents/graph.py` | End-to-end test: config → strategy advice |
| Final report | `src/output/report.py` | Visual test: strategy sections in report |

**Key constraint**: `--use-agents` flag controls new vs old pipeline. Both produce valid reports.

### Migration Strategy

1. Each phase produces working code that can be tested independently
2. `--use-agents` flag activates new pipeline; default remains old pipeline
3. After Phase 4, validate new pipeline output quality against old pipeline
4. Once quality confirmed, swap default to new pipeline
5. Deprecate old pipeline after one release cycle with both available

## 13. Key Data Structures

### 13.1 News Schemas

```python
@dataclass
class SearchPlan:
    fund_code: str
    stock_codes: list[str]           # Top holdings codes
    stock_weights: dict[str, float]  # code → weight
    sectors: list[str]               # SW industries
    themes: list[str]                # Investment themes
    macro_queries: list[str]        # Macro search terms

@dataclass
class ClassifiedNewsItem:
    title: str
    content: str
    source: str
    date: str
    layer: int                       # 1-6
    layer_weight: float              # 0.2-1.0
    entities: list[str]              # Stock/industry codes mentioned
    relevance_score: float           # Multi-factor relevance
    vector_similarity: float        # Qdrant cosine similarity
    ai_rank: int | None             # LLM rerank position
    research_summary: dict | None   # Research-style summary

@dataclass
class ExtractedEvent:
    event_id: str
    event_type: str                  # From taxonomy
    subtype: str
    entities: list[str]              # Affected stock/industry codes
    polarity: float                  # -1.0 to 1.0
    magnitude: float                 # 0.0 to 1.0
    time_horizon: Literal["short", "medium", "long"]
    description: str
    source_news_ids: list[str]
```

### 13.2 Scoring Schemas

```python
@dataclass
class ScoreComponent:
    score: float                      # 0-100
    detail: dict                      # Sub-factor breakdown
    weights: dict[str, float]        # Dynamic weights used
    confidence: float                 # 0-1

class MarketRegime(Enum):
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    TRENDING = "trending"
    CRISIS = "crisis"

@dataclass
class CompositeScore:
    quant_score: ScoreComponent
    fundamental_score: ScoreComponent
    event_score: ScoreComponent
    position_score: ScoreComponent
    timing_score: ScoreComponent
    weights_used: dict[str, float]
    composite: float                  # Weighted sum
    level: Literal["green", "yellow", "orange", "red"]
    regime: MarketRegime
```

### 13.3 Strategy Schemas

(Defined in Section 6.2 — StrategyAdvice, StrategyAction, StrategyState)