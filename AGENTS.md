# Fund-Agent Development Guide

## Project Overview
AI-driven multi-agent fund research platform. Transforms fund analysis from keyword-based rules to KG+vector+AI pipeline.

## Architecture
- `src/kg/` — Knowledge Graph (NetworkX), string-ID nodes
- `src/vectorstore/` — Qdrant vector DB
- `src/news/` — 8-stage holdings-driven news pipeline
- `src/analysis/scoring/` — 5-dimension AI+factor scoring
- `src/strategy/` — Strategy engine (state machine)
- `src/agents/graphs/` — LangGraph multi-agent nodes

## Development Commands
```bash
# Run all tests
PYTHONPATH=. python -m pytest tests/ -v

# Run specific module tests
PYTHONPATH=. python -m pytest tests/test_kg_*.py -v

# Generate report (old pipeline)
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md

# Generate report (new pipeline)
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --use-agents

# Run Streamlit UI
python3 -m src.cli ui -c fund-portfolio.yaml -p 8501
```

## Environment
```bash
# Required
export FINNHUB_API_KEY="your_key"   # US stock news
export TAVILY_API_KEY="your_key"    # AI search supplement
# Optional
export FUND_REPORT_CUTOFF_HOUR=22
export FUND_DCA_CUTOFF_HOUR=10
```

## Test Patterns
- Use `unittest.TestCase` or `pytest` classes
- Mock external APIs with `sys.modules` pattern (see test_news_fetcher.py)
- NetworkX KG uses string IDs: `"fund:110011"`, `"stock:600519"`
- Dataclass instances stored in `G.nodes[id]["data"]`
- Run with `PYTHONPATH=.` to resolve `src.` imports

## Key Design Decisions
- KG nodes use string IDs, not objects (for NetworkX compatibility)
- All scoring modules have rule-based fallbacks (no LLM dependency)
- New pipeline activated via `--use-agents` flag (backward compatible)
- `conftest.py` adds project root to `sys.path` for pytest
