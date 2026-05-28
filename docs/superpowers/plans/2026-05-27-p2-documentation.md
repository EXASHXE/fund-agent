# P2: Documentation & Workflow Update Plan

## Task A: Update README.md

File: `README.md`

Changes needed:
1. **Architecture tree** — Replace old flat `src/` layout with new modular structure showing:
   - `src/kg/` — Knowledge Graph (NetworkX)
   - `src/vectorstore/` — Qdrant vector database
   - `src/events/` — Event taxonomy + extraction
   - `src/news/` — 8-stage holdings-driven news pipeline (NEW) + Finnhub/Tavily clients
   - `src/analysis/scoring/` — 5-dimension AI+factor scoring (NEW)
   - `src/strategy/` — Strategy engine with state machine (NEW)
   - `src/agents/` — LangGraph multi-agent system (NEW)
   - `src/agents/graphs/` — 5 specialized agent nodes + supervisor

2. **Feature list** — Add: knowledge graph analysis, vector search, event extraction, 8-stage news pipeline, 5-dimension scoring, regime-aware strategy engine, LangGraph multi-agent orchestration, Finnhub US news, Tavily AI search

3. **Scoring architecture** — Replace 3-factor (macro/meso/micro) with 5-dimension (QuantScore/FundamentalScore/EventScore/PositionScore/TimingScore) with regime-adaptive weights

4. **Quick start** — Add `--use-agents` flag example, news API key setup

## Task B: Update Skills & Prompts

### B1: `skills/fund-analyst/SKILL.md`
- Update workflow section to reflect new `--use-agents` CLI flag
- Add reference to LangGraph agents as the core analysis engine

### B2: `skills/fund-analyst/prompts/scoring-agent.md`
- Update to work with new 5-dimension scoring output
- Old: macro/meso/micro (0-20, 0-30, 0-50)
- New: quant/fundamental/event/position/timing (each 0-100, regime-weighted)

### B3: `skills/fund-analyst/references/evidence-contract.md`
- Add new scoring dimensions to quant_baseline schema

### B4: `skills/fund-analyst/references/decision-contract.md`
- Add strategy_advice section (from StrategyEngine output)

## Task C: Create Missing Files

### C1: `AGENTS.md`
- Project-level AI agent configuration with development commands, test patterns, module architecture overview

### C2: `pyproject.toml`
- Standard Python packaging config with pytest settings

### C3: `.github/workflows/ci.yml`
- CI pipeline: install deps, run pytest on push/PR