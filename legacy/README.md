# Legacy Pipeline — Retained for Reference

## Overview

The legacy `analyze` pipeline (CLI → data fetch → quant scoring → news pipeline → report) has been
moved from `src/` to `legacy/` for architecture separation. All legacy modules live under `legacy/` —
the `src/` directory is now exclusively the new Research OS path.

## Components

### Old CLI Analyze Main Path
- **Location**: `legacy/cli.py`, `legacy/routes/commands.py`
- **Flow**: CLI → `legacy.workflows.analyze` → `legacy.workflows.workflow.run_analyze`
- **Compat shim**: `src/cli.py` re-exports `legacy.cli.main` with DeprecationWarning

### Old News Pipeline
- **Location**: `legacy/news/` + `legacy/deprecated/news_pipeline.py`
- **Purpose**: 8-stage holdings-driven news pipeline (entity mapping → fetching → dedup → sentiment → catalyst scoring → NAV correlation)
- **Replaced by**: Research OS Skill pipeline (`src/core/research_os.py`)

### Old Scoring Pipeline
- **Location**: `legacy/analysis/scoring/`, `legacy/deprecated/scorer.py`
- **Purpose**: Multi-dimensional fund scoring engine (Quant, Fundamental, Event, Position, Timing)
- **Replaced by**: `src/tools/quant/` (pure math) + Research OS evidence pipeline

### Old Strategy / Recommendation Engine
- **Location**: `legacy/strategy/` (state machine: WAIT→HOLD→ADD→REDUCE→STOP_LOSS)
- **Location**: `legacy/deprecated/` (macro.py, meso.py, micro.py — IF/ELIF rules)
- **Replaced by**: `src/core/decision_engine.py` (contract-enforced); `src/core/critic.py` (structural review)

### Old Report Rendering
- **Location**: `legacy/output/`
- **Purpose**: Markdown/JSON report generation
- **Replaced by**: DecisionContract v2 + ExecutionLedger

### Old Agent System
- **Location**: `legacy/agents/` (8-node LangGraph multi-agent)
- **Replaced by**: New standalone Planner/Critic/DecisionEngine in `src/core/`

## Architecture Boundary Rules

1. **`src/core/`**, **`src/schemas/`**, **`src/graph/`**, **`src/tools/`**, **`src/workflows/`**, **`src/infra/`**
   MUST NOT import from `legacy/`.
2. **Legacy** CAN import from `src/tools/`, `src/schemas/`, and `src/infra/`.
3. Legacy should prefer `src.infra.config`, `src.infra.data`, `src.infra.persistence`, and `src.infra.vectorstore`.
   The old `src.config`, `src.data`, `src.db`, and `src.vectorstore` packages are deprecated package-level shims only.
4. **`src/tools/`** must remain pure: no LLM, no network IO.
5. **Architecture tests** enforce all boundaries in `tests/test_architecture_boundaries.py`.
6. The legacy tree is a compatibility/reference path only; new Research OS code belongs under `src/`.

## Migration Path

1. Existing CLI (`python3 -m src.cli analyze`) works via compat shim → `legacy/cli.py`
2. New Research OS: `from src.core.research_os import run_research_task`
3. Both paths coexist; no breaking changes.
