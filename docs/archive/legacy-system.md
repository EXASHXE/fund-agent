# Legacy System — Historical Reference

The legacy `fund-agent` system was preserved before `v0.1.0-skillpack-alpha`.
It has been removed from the current mainline.

## Historical Modules

The legacy system included:

- `legacy/analysis/` — multi-dimensional scoring engine
- `legacy/news/` — holdings-driven news pipeline and provider clients
- `legacy/output/` — Markdown/JSON report rendering
- `legacy/strategy/` — WAIT/HOLD/ADD/REDUCE/STOP_LOSS state machine
- `legacy/workflows/` — workflow orchestration
- `legacy/decision/` — decision support modules
- `legacy/engine/` — calculation engine
- `legacy/events/` — event taxonomy
- `legacy/prompts/` — prompt templates
- `legacy/recommend/` — recommendation engine
- `legacy/cli.py` — CLI entrypoint stub
- `tests/deprecated/` — legacy test suite

These modules are not part of the host-agnostic plugin contract.

## How To Inspect

To inspect the old implementation, checkout the alpha tag:

```bash
git checkout v0.1.0-skillpack-alpha
```

## Current Plugin Core

The current `fund-agent` is a host-agnostic AI Financial Research Skill Pack
/ Agent Plugin. The plugin core lives in:

- `skillpack/` — manifest, capabilities, tools, contracts
- `skills/` — host-readable skill instructions
- `src/skills_runtime/` — host-callable skill handlers
- `src/schemas/` — typed contracts
- `src/tools/` — pure tools and MCP adapter boundary
- `src/graph/` — KnowledgeGraph helpers
- `src/skillpack/` — manifest loader, resolver, validator

Do not reintroduce legacy modules into `src` or `skillpack`.
