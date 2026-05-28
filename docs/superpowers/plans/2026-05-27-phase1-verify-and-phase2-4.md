# Phase 1 Verification + Phase 2-4 Implementation Plan

## Current State

### Phase 1: Infrastructure (DONE, needs verification)
All source files created/modified:
- `src/kg/schema.py` — Mutable dataclasses with `@property id` and `node_type`
- `src/kg/graph.py` — KnowledgeGraphBuilder with string-ID NetworkX pattern
- `src/kg/enrichment.py` — enrich_with_events with string-ID pattern
- `src/kg/industry_map.py` — SW industry → theme mapping
- `src/events/taxonomy.py` — EventType, EventCategory, classify_event
- `src/events/extractor.py` — extract_events_from_text stub
- `src/vectorstore/collections.py` — CollectionSchema, COLLECTIONS dict
- `src/vectorstore/embedding.py` — EmbeddingPipeline
- `src/vectorstore/client.py` — get_qdrant_client, init_collections
- `src/vectorstore/search.py` — cosine_similarity, find_similar_funds
- `src/analysis/scoring/types.py` — ScoreComponent, MarketRegime, CompositeScore
- `src/agents/state.py` — FundResearchState TypedDict with EMPTY_STATE
- `src/agents/supervisor.py` — AGENT_ORDER, get_supervisor_routing
- `conftest.py` — sys.path for pytest
- `__init__.py` files updated for kg, events, vectorstore, agents, scoring

All test files created:
- `tests/test_kg_schema.py` — Schema + industry map tests
- `tests/test_kg_graph.py` — Graph builder, query, enrichment tests
- `tests/test_vectorstore.py` — Collection + cosine similarity tests
- `tests/test_event_taxonomy.py` — Taxonomy + scoring types tests
- `tests/test_agents_state.py` — State + supervisor routing tests

### Key Design Decisions (already applied)
- NetworkX uses string IDs (`"fund:110011"`) as nodes, dataclass instances stored as `G.nodes[id]["data"]`
- Dataclasses are mutable (not frozen) — ThemeNode.keywords is `list[str]`
- KGNode base class removed — no inheritance, just standalone dataclasses
- conftest.py adds project root to sys.path for pytest

---

## Task 1: Verify Phase 1 (URGENT — unblocks everything)

**Files to verify:**
- All Phase 1 source and test files listed above

**Steps:**
1. Run `PYTHONPATH=. python -m pytest tests/test_kg_schema.py tests/test_kg_graph.py tests/test_vectorstore.py tests/test_event_taxonomy.py tests/test_agents_state.py -v --tb=short`
2. If tests fail, fix the failures
3. Run `PYTHONPATH=. python -m pytest tests/ -v --tb=short` to verify no regressions in existing 89 tests
4. If any existing tests break, fix them (but only breakages caused by Phase 1 changes)

**Known issues to check:**
- `src/kg/__init__.py` imports KGNode which no longer exists → ALREADY FIXED (removed)
- `src/kg/graph.py` imports KGNode → ALREADY FIXED (removed from import)
- NetworkX G.add_node() was using objects instead of string IDs → ALREADY FIXED (uses `.id` now)
- ThemeNode.keywords was `tuple[str, ...]` → ALREADY changed back to `list[str]` with `field(default_factory=list)`
- conftest.py may need `PYTHONPATH=.` for pytest to find `src` module

---

## Task 2: Phase 2 — News System Restructure

**Goal:** Replace keyword-based news pipeline with holdings-driven KG+vector+AI pipeline.

**New files to create:**
- `src/news/pipeline.py` — RetrieverPipeline orchestrator (8 stages)
- `src/news/retriever.py` — Holdings-driven news retrieval
- `src/news/classifier.py` — 6-layer news classification
- `src/news/scorer.py` — Multi-factor relevance scoring + KG overlap
- `src/news/summarizer.py` — Research-style AI summary
- `src/news/schemas.py` — SearchPlan, ScoredNews, ResearchSummary data models

**Refactor (keep, adapt):**
- `src/news/evaluator.py` — Add quality metrics
- `src/news/news_fetcher.py` — Keep as data source, refactor retrieval logic

**Replace (delete or deprecate):**
- `src/news/sentiment.py` → replaced by `src/news/scorer.py`
- `src/news/agent_context.py` → replaced by LangGraph state

**Dependencies:** Phase 1 (KG, events, vectorstore) must pass tests first.

**Testing:** Create `tests/test_news_pipeline.py`, `tests/test_news_classifier.py`, `tests/test_news_scorer.py`

---

## Task 3: Phase 3 — Scoring System (AI+Factor Hybrid)

**Goal:** Replace keyword→int lookup scoring with dynamic 5-dimension scoring.

**New files to create:**
- `src/analysis/scoring/quant.py` — QuantScore (preserve existing metrics, add regime weights)
- `src/analysis/scoring/fundamental.py` — FundamentalScore (AI-driven, uses KG + events)
- `src/analysis/scoring/event.py` — EventScore (from news pipeline + KG impact chains)
- `src/analysis/scoring/position.py` — PositionScore (enhanced holdings analysis)
- `src/analysis/scoring/timing.py` — TimingScore (AI judgment)
- `src/analysis/scoring/regime.py` — MarketRegimeDetector (LLM-assisted)

**Refactor (keep, enhance):**
- `src/analysis/scoring/macro.py` → Preserve as fallback, wrap in QuantScore
- `src/analysis/scoring/meso.py` → Replace logic with FundamentalScore
- `src/analysis/scoring/micro.py` → Preserve data-driven parts, wrap in PositionScore

**Existing types (already created):**
- `src/analysis/scoring/types.py` — ScoreComponent, MarketRegime, CompositeScore, score_level

**Dependencies:** Phase 1 (KG, events) + Phase 2 (news pipeline for EventScore).

**Testing:** Create `tests/test_scoring_*.py` for each new scorer.

---

## Task 4: Phase 4 — Strategy Engine + LangGraph Agents

**Goal:** Replace stub agents with LangGraph multi-agent system.

**New files to create:**
- `src/strategy/engine.py` — StrategyEngine with state machine (buy/hold/sell/reduce)
- `src/strategy/models.py` — StrategyDecision, TriggerPoint, ActionPlan
- `src/agents/graphs/supervisor.py` — LangGraph StateGraph with routing logic
- `src/agents/graphs/news_agent.py` — NewsAgent graph node
- `src/agents/graphs/quant_agent.py` — QuantAgent graph node
- `src/agents/graphs/research_agent.py` — ResearchAgent graph node
- `src/agents/graphs/risk_agent.py` — RiskAgent graph node
- `src/agents/graphs/strategy_agent.py` — StrategyAgent graph node
- `src/agents/tools/` — Tool definitions for each agent

**Refactor (keep, adapt):**
- `src/agents/state.py` — Already created (FundResearchState)
- `src/agents/supervisor.py` — Already created (AGENT_ORDER, get_supervisor_routing)
- `src/agents/protocols.py` — Keep AgentOpinion contract

**Dependencies:** Phase 1 + Phase 2 + Phase 3 all complete.

**Testing:** Create `tests/test_strategy.py`, `tests/test_agent_graphs.py`.

---

## Execution Order

1. **Task 1** (verify Phase 1) — MUST pass before anything else
2. **Task 2** (Phase 2: News) — Can start after Task 1 passes
3. **Task 3** (Phase 3: Scoring) — Can start after Task 1 passes, but needs Phase 2 for EventScore
4. **Task 4** (Phase 4: Strategy + Agents) — Needs all previous phases