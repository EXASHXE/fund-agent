# AI Financial Research OS — Development Guide

## Project Overview

AI-native Financial Research OS — a host-injectable Skill Pack invoked by LLM agents. Transforms fund analysis from keyword-based rules to AI-native pipeline: Skill → ToolRegistry → KG query → MCP adapter → EvidenceGraph → ExecutionLedger.

## Architecture

```
skills/                    # 4 AI-native Skills (LLM invocation entry points)
├── fund_analysis/         #   CIO-level strategic evaluation
├── news_research/         #   Holdings-driven news pipeline
├── sentiment_analysis/    #   Polarity/intensity/time-decay analysis
└── thesis_generation/     #   Thesis → Decision → Ledger pipeline

src/
├── schemas/               # Typed contracts (evidence-contract.v2, decision-contract.v2)
│   ├── evidence.py        #   EvidenceItem: HardEvidence / SoftEvidence / HybridEvidence
│   ├── decision.py        #   Decision + ActionType + ExecutionLedger
│   └── evidence_graph.py  #   EvidenceGraph: dedup, conflict detection, hybrid upgrade
├── tools/                 # Pure math functions (no IO/network/LLM)
│   ├── registry.py        #   ToolRegistry: register, invoke, bind
│   └── evidence_tools.py  #   Read-only evidence query tools
├── kg/                    # Knowledge Graph (NetworkX), string-ID nodes
├── graph/                 # KG query interfaces
├── vectorstore/           # Qdrant vector DB
├── news/                  # 8-stage holdings-driven news pipeline
├── agents/                # LangGraph multi-agent system
│   └── graphs/            #   8 nodes: planner → news → quant → risk → research
│                           #   → critic → strategy → ledger (with iteration loop)
│       ├── planner_agent.py   #   Research plan generation
│       ├── critic_agent.py    #   Evidence review (triggers iteration loop)
│       └── ledger_node.py     #   ExecutionLedger output
├── analysis/scoring/      # 5-dimension AI+factor scoring, dynamic weights
├── strategy/              # Strategy state machine (WAIT/HOLD/ADD/REDUCE/STOP_LOSS)
├── workflows/             # Thin orchestration entry (no business logic)
├── core/                  # Workflow orchestration & contract validation
├── deprecated/            # Legacy pipeline (isolated, does not affect mainline)
└── cli.py                 # Thin CLI wrapper for local debugging only
```

## Skill Invocation Model

### Primary: LLM Agent loads Skill

```
Host (Claude/GPT/Gemini) loads fund-analyst Skill
  → Skill declares MCP capabilities (TrendRadar, Tavily, Finnhub, ...)
    → Host injects the required MCP adapters
      → Skill orchestrates: ToolRegistry tools + KG queries + MCP adapters
        → 8-node LangGraph executes
          → Outputs: EvidenceGraph + Decision[] + ExecutionLedger
```

### Secondary: CLI for local debugging

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md
python3 -m src.cli ui -c fund-portfolio.yaml -p 8501
```

CLI is a thin wrapper for local development/testing. All business logic lives in `skills/`, `src/tools/`, `src/agents/`.

## Development Commands

```bash
# Run all tests (971 tests)
PYTHONPATH=. python -m pytest tests/ -v

# Run specific module tests
PYTHONPATH=. python -m pytest tests/test_kg_*.py -v
PYTHONPATH=. python -m pytest tests/test_skill_*.py -v
PYTHONPATH=. python -m pytest tests/test_schemas_*.py -v
PYTHONPATH=. python -m pytest tests/test_agents_*.py -v

# CLI local testing (thin wrapper)
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md

# Run Streamlit UI (local development)
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
- Skill tests verify ToolRegistry integration (see test_skill_structure.py, test_skill_classes.py)
- Schema tests verify contract validation (see test_schemas_evidence.py, test_schemas_decision.py)

## Key Design Decisions

- **KG nodes use string IDs**, not objects (for NetworkX compatibility)
- **All scoring modules have rule-based fallbacks** (no LLM dependency)
- **HardEvidence confidence_weight is always 1.0** (pure computation)
- **Skills use ToolRegistry** — no direct network calls inside skills
- **8-node LangGraph with iteration loop**: Critic reviews output → loops to Planner if gaps found (max 3 iterations)
- **EvidenceGraph supports hybrid upgrades**: SoftEvidence → HybridEvidence when 2+ sources corroborate
- **Legacy code isolated in `src/deprecated/`** — does not affect mainline agent pipeline
- **`conftest.py`** adds project root to `sys.path` for pytest
- **CLI is a thin wrapper** — all business logic lives in `src/tools/`, `src/schemas/`, `src/agents/`, `skills/`
- **Skills are pure Python** — no network/IO calls; MCP adapters injected by host
