# AGENTS.md — Coding Agent Integration Guide

## Project Identity

`fund-agent` is a **host-agnostic financial research skill pack / agent plugin**.
It is **not an autonomous agent runtime**. External agents (OpenCode, Claude Code,
Codex, OpenClaw, Hermes) own planning and orchestration.

At the skill layer, `fund-agent` is **Markdown-first**. `skills/<slug>/SKILL.md`
files are the primary agent-facing workflow and policy instructions. Python
under `src/` is deterministic runtime, schema, and tool implementation support.

## What Agents Should Use

Primary entrypoints and resources:

- `skillpack/fund-agent.skillpack.yaml` — plugin manifest (start here)
- `skills/README.md` — Markdown skill directory policy
- `skills/<slug>/SKILL.md` — primary agent-facing skill instructions
- `skills/<slug>/references/*.md` — detailed policy, examples, templates
- `docs/agent-host-quickstart.md` — host integration quickstart
- `docs/host-integration.md` — detailed integration guide
- `docs/plugin-api.md` — full API reference
- `docs/contracts/report-output-contract.v1.md` — report output shape contract
- `docs/install/opencode.md` — OpenCode plugin install (first native target)
- `docs/install/manual-host.md` — manual / Python host install
- `docs/install/codex.md` — Codex install (manual / light)
- `docs/design/runtime-bridge.md` — runtime bridge design (thin CLI shipped; deeper bridge future)
- `src/skills_runtime/` — host-callable skill handlers
- `src/schemas/` — typed contracts
- `src/tools/` — pure tools and MCP adapter boundary
- `src/tools/portfolio/report_composer.py` — deterministic report sections
- `src/graph/` — KnowledgeGraph helpers
- `src/tools/adapters/mcp.py` — MCP adapter abstraction

## What Agents Must NOT Use As Primary Path

- Do NOT use `legacy` as runtime code.
- Do NOT use `src.core.research_os` as a required host integration path.
- Do NOT import provider SDKs (tavily, finnhub, exa, firecrawl, reddit,
  akshare, openai, anthropic, langchain) inside skills.
- Do NOT add network calls outside `MCPHostAdapter` boundary.
- Do NOT generate formal `Decision` objects outside `DecisionSupportSkill`.
- Do NOT infer runtime skill IDs from folder names.
- Do NOT treat `fund-analyst` as a runtime entrypoint; it is legacy/reference-only.

## Recommended Agent Workflow

1. Read the skill pack manifest: `skillpack/fund-agent.skillpack.yaml`
2. Inspect `skillpack/capabilities.yaml` and `skillpack/tools.yaml`
3. Read `skills/README.md` and the relevant hyphenated `skills/<slug>/SKILL.md`
4. Resolve the skill runtime class for the manifest skill ID you need
5. Construct a `SkillInput` (schema: `src/schemas/skill.py`)
6. Inject a `MCPHostAdapter` implementation if the skill needs MCP data
7. Call `skill.run(skill_input)`
8. Collect `SkillOutput.evidence_items` from the result
9. For fund_analysis, use `compose_personal_fund_report(artifacts)` for
   deterministic report sections (`report_sections`, `report_outline`,
   `report_quality_gate`); hosts may render via `render_report_markdown`.
10. Call `compile_evidence_graph(evidence_items)` to consolidate evidence
11. Call `DecisionSupportSkill` when you need a formal `Decision`
12. Return `Decision` / `ExecutionLedger` to the user

## Skill Map

| Skill | Runtime | Requires MCP | Produces | Forbidden |
|---|---|---|---|---|
| `fund_analysis` | `src.skills_runtime.fund_analysis:FundAnalysisSkill` | none | `HardEvidence`, `report_sections`, `report_outline`, `report_quality_gate`, `data_completeness` | `Decision`, `ExecutionLedger` |
| `news_research` | `src.skills_runtime.news_research:NewsResearchSkill` | `web_search`, `financial_news` | `SoftEvidence` | — |
| `sentiment_analysis` | `src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill` | `social_sentiment` | `SoftEvidence` | — |
| `thesis_generation` | `src.skills_runtime.thesis_generation:ThesisGenerationSkill` | none | `ThesisDraft` | `formal_decision_generation` |
| `decision_support` | `src.skills_runtime.decision_support:DecisionSupportSkill` | none | `Decision`, `ExecutionLedger` | — |

Canonical Markdown doc slugs are hyphenated: `fund-analysis`,
`news-research`, `sentiment-analysis`, `thesis-generation`, and
`decision-support`. Underscore directories under `skills/` are compatibility
only when retained.

## Safety / Contract Rules

- `HardEvidence` confidence_weight MUST be 1.0.
- `SoftEvidence` requires `source_type`, `timestamp`, and `related_entities`.
- Only `decision_support` may produce formal `Decision` and `ExecutionLedger`.
- Active decisions (`BUY`, `SELL`, `INCREASE`, `REDUCE`) REQUIRE evidence anchors.
- `WAIT` / `HOLD` may be used when evidence is insufficient.
- `SkillOutput.errors` MUST use standard error codes (see `docs/plugin-api.md`).

## Testing Commands

```bash
# Default plugin test gate
PYTHONPATH=. pytest -q

# Full health check
bash scripts/check_plugin_gate.sh

# External host integration smoke test
PYTHONPATH=. pytest tests/integration/test_external_host_smoke.py -q

# Architecture boundaries
PYTHONPATH=. pytest tests/architecture/test_architecture_boundaries.py -q

# Runtime bridge CLI tests
PYTHONPATH=. pytest tests/runtime_bridge -q

# Minimal host demo
python examples/minimal_host_news_to_decision.py

# Runtime bridge CLI smoke
python scripts/run_skill.py --list-skills --pretty
python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_fund_analysis_input.json --pretty
```

## Versioning

- Current package version is read from `VERSION`.
- Skillpack manifest version must match `VERSION`.
- Contract schema version is `skillpack.v1`.
- Breaking contract changes require `schema_version` bump.

## Before You Modify

Agents must run:

```bash
PYTHONPATH=. pytest -q
bash scripts/check_plugin_gate.sh
```

When changing install surface (OpenCode plugin, package.json, install
docs, runtime-bridge design), also run:

```bash
PYTHONPATH=. pytest tests/install -q
```

Before changing runtime contracts, also update:

- `docs/CONTRACT_FREEZE.md`
- `docs/contracts/report-output-contract.v1.md`
- `skillpack/fund-agent.skillpack.yaml`
- `tests/contracts`
- `tests/skillpack`

## RC Validation

Before tagging an RC, agents must run:

```bash
PYTHONPATH=. pytest -q
bash scripts/check_plugin_gate.sh
python examples/minimal_host_news_to_decision.py
python scripts/check_examples.py
```

Also verify:

- `VERSION` == manifest version == pyproject version
- `legacy/` contains only `README.md`
- `tests/deprecated` does not exist
- No provider SDK in `skills_runtime`

## Minimal Example

See `examples/minimal_host_news_to_decision.py` for a complete,
self-contained host integration flow using only in-memory adapters.
