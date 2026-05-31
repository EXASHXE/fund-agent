# Legacy Archive — Historical Reference Only

## Overview

The legacy pipeline is preserved as a historical archive. It is not part of the
host-agnostic plugin contract and is not required for host integration.

## Plugin Replacement

The legacy pipeline has been replaced by the host-agnostic Skill Pack:

- `skillpack/fund-agent.skillpack.yaml` — plugin manifest
- `src/skills_runtime/` — host-callable skill handlers
- `src/tools/` — pure quant, ledger, evidence tools
- `src/schemas/` — typed contracts (Skill, Evidence, Decision)
- `src/graph/` — KnowledgeGraph helpers
- `src.tools.evidence.validators.compile_evidence_graph` — evidence compiler
- `src.skills_runtime.decision_support.DecisionSupportSkill` — formal decisions
- `src.tools.adapters.mcp.MCPHostAdapter` — MCP adapter boundary

## Archive Boundary

- No new code should import `legacy`.
- No new tests should depend on `legacy`.
- Provider-specific clients here are not part of the plugin contract.
- Legacy may be deleted after an archive tag.
- Legacy is not included in the default pytest gate.

## Remaining Components

- `legacy/analysis/` — old multi-dimensional scoring engine
- `legacy/news/` — old holdings-driven news pipeline and provider clients
- `legacy/output/` — old Markdown/JSON report rendering
- `legacy/strategy/` — old WAIT/HOLD/ADD/REDUCE/STOP_LOSS state machine
- `legacy/workflows/` — old workflow orchestration
- `legacy/cli.py` — DEPRECATED stub (routes/services deleted)
- `legacy/deprecated/` — historical pipeline experiments
- `legacy/engine/`, `legacy/events/`, `legacy/prompts/`, `legacy/recommend/`, `legacy/decision/` — legacy support modules

## Deleted Directories

The following low-value legacy directories have been removed:

- `legacy/ui/` — old Streamlit UI (zero references)
- `legacy/routes/` — old CLI router
- `legacy/services/` — old service layer
- `legacy/agents/` — old LangGraph multi-agent experiment
- `legacy/forecast/` — old trend forecast engine
