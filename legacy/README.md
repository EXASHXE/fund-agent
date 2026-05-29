# Legacy Pipeline — Retained for Reference

## Overview

The legacy `analyze` pipeline (CLI → data fetch → quant scoring → news pipeline → report) is isolated in `src/deprecated/`. This document describes what was replaced and the migration path.

## Components

### Old CLI Analyze Main Path
- **Location**: `src/cli.py`, `src/routes/commands.py`
- **Flow**: CLI → `src.workflows.run_analyze` → `src.core.workflow.run_analyze`
- **Status**: Works but does not use the new Research OS architecture

### Old News Pipeline
- **Location**: `src/deprecated/news_pipeline.py` (383 lines)
- **Purpose**: 8-stage holdings-driven news pipeline (entity mapping → fetching → dedup → sentiment → catalyst scoring → NAV correlation)
- **Replaced by**: 8-node LangGraph multi-agent system in `src/agents/`

### Old Scoring Pipeline
- **Location**: `src/deprecated/scorer.py` (285 lines)
- **Purpose**: Single-fund scoring card engine (20% macro, 30% meso, 50% micro) with hardcoded rules
- **Replaced by**: `src/analysis/scoring/` — 5-dimension AI+factor scoring engine

### Old Recommendation Engine
- **Location**: `src/deprecated/` (macro.py, meso.py, micro.py)
- **Purpose**: IF/ELIF name-matching rules for fund recommendations
- **Replaced by**: `src/strategy/` — state machine strategy engine (WAIT→HOLD→ADD→REDUCE→STOP_LOSS)

### Old Report Rendering
- **Location**: `src/output/`
- **Purpose**: Markdown/JSON report generation from old pipeline
- **Replaced by**: DecisionContract v2 + ExecutionLedger

## Architecture Boundary Rules

1. **New core modules** (`src/core/`, `src/workflows/`, `src/tools/`) MUST NOT import from `src/deprecated/`
2. **Legacy** CAN import new tools (e.g., `src/deprecated/scorer.py` imports `src.analysis.*`)
3. **New modules** use pure tool functions only — no LLM/network/IO in `src/tools/`

## Migration Path

For existing users:
1. Existing CLI path (`python3 -m src.cli analyze`) continues to work
2. New Research OS path: `from src.core.research_os import run_research_task`
3. Both paths coexist; no breaking changes
