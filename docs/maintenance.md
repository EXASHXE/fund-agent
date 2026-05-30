# Maintenance Guide

## Plugin Core

Plugin core is the host-facing contract surface:

- `skillpack/` manifests, capabilities, tools, contracts, and examples.
- `skills/` host-readable `SKILL.md` instructions.
- `src/skills_runtime/` host-callable skill handlers.
- `src/schemas/` typed skill, evidence, graph, decision, and ledger contracts.
- `src/tools/` pure tools, evidence compilation, and MCP adapter boundary.
- `src/graph/` KnowledgeGraph helpers.

Core code must not import `legacy`, provider SDKs, network clients, or LLM SDKs.
External hosts own orchestration, credentials, network access, and retries.

## Legacy Archive

`legacy/` is historical reference only. Do not add new imports from plugin core
to legacy modules, and do not make new main-gate tests depend on legacy. Legacy
provider clients are not part of the plugin contract and may be removed after
an archive tag.

ResearchOS modules under `src/core` and `src/workflows` are deprecated optional
reference workflows. They are not required for host integration.

## Main Test Gate

Default `pytest` targets plugin core only:

- `tests/architecture`
- `tests/contracts`
- `tests/skillpack`
- `tests/skills`
- `tests/tools`
- `tests/integration`

Historical workflow and legacy tests live under `tests/deprecated` and can be
run explicitly with `PYTHONPATH=. pytest tests/deprecated -q`.

## Adding A Skill

1. Add or update the host-readable `skills/<skill-name>/SKILL.md`.
2. Add a host-callable runtime class under `src/skills_runtime/`.
3. Use `SkillInput` and `SkillOutput` only for runtime boundaries.
4. Return `EvidenceItem` objects or draft artifacts as appropriate.
5. Register the skill in `skillpack/fund-agent.skillpack.yaml`.
6. Add examples under `skillpack/examples/`.
7. Add main-gate tests under `tests/skills` or `tests/skillpack`.

Only `DecisionSupportSkill` may produce formal `Decision` and
`ExecutionLedger` artifacts.

## Adding MCP Capability Declarations

Declare new MCP capability names in `skillpack/capabilities.yaml` and reference
them from the relevant skill in `skillpack/fund-agent.skillpack.yaml`.

Do not add Tavily, Finnhub, Exa, Firecrawl, Reddit, or other provider SDKs to
the plugin core. Implement provider-specific networking in the external host and
adapt it through `src.tools.adapters.mcp.MCPHostAdapter`.
