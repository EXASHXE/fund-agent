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

- `legacy/cli.py` — DEPRECATED stub
- `legacy/analysis/` — old multi-dimensional scoring engine
- `legacy/decision/` — legacy decision support modules
- `legacy/deprecated/` — historical pipeline experiments
- `legacy/engine/` — old calculation engine
- `legacy/events/` — old event taxonomy
- `legacy/news/` — old holdings-driven news pipeline and provider clients
- `legacy/output/` — old Markdown/JSON report rendering
- `legacy/prompts/` — old prompt templates
- `legacy/recommend/` — old recommendation engine
- `legacy/strategy/` — old WAIT/HOLD/ADD/REDUCE/STOP_LOSS state machine
- `legacy/workflows/` — old workflow orchestration
