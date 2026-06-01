# fund-agent: Host-Agnostic AI Financial Research Skill Pack

> Host-Agnostic AI Financial Research Skill Pack / Agent Plugin.

`fund-agent` is a discoverable skill pack for external agent hosts such as
OpenCode, Claude Code, Codex, OpenClaw, Hermes, and similar runtimes. The host
agent owns planning and orchestration. This repository provides callable
financial research skills, typed contracts, evidence tools, KnowledgeGraph
helpers, and a host-native MCP adapter boundary.

`fund-agent` is not an internal autonomous ResearchOS runtime, not a fixed
Planner loop, and not a production agent server.

## Overview

`fund-agent` packages financial research capabilities so an external agent can
mount them as a plugin. It does not require a resident autonomous runtime.

## What This Repository Provides

- `skillpack/fund-agent.skillpack.yaml`: primary manifest and host entrypoint
- `skillpack/capabilities.yaml`: host MCP capability declarations
- `skillpack/tools.yaml`: callable tool declarations
- `skillpack/contracts.yaml`: schema and contract declarations
- `skills/SKILL.md`: host-readable skill pack index
- `skills/`: human-readable skill instructions and per-skill `SKILL.md` assets
- `src/skills_runtime/`: host-callable Python skill handlers
- `src/tools/`: pure fund, portfolio, quant, ledger, evidence, and adapter tools
- `src/schemas/`: typed contracts for skill, fund, evidence, graph, decision, ledger
- `src/graph/`: KnowledgeGraph implementation and query helpers
- `src/tools/adapters/mcp.py`: host-native MCP adapter abstraction

The external host decides which skill to call, in what order, with which MCP
provider implementations, and how to use the returned evidence.

## What The External Host Owns

- planning and orchestration
- task memory and retry policy
- MCP provider implementation and credentials
- provider rate limits and network access
- final user interaction and UX

## Not The Main Product

- internal ResearchOS
- internal Planner loop
- internal Agent runtime
- fixed LangGraph-style orchestration

Reference workflow examples may exist under `examples/reference_workflows/`, but
they are optional examples only. Host integrations do not need to import or call
`src.core.research_os`.

## Skill Pack Manifest

The standard plugin entrypoint is
`skillpack/fund-agent.skillpack.yaml`. It declares runtime classes, schemas,
contracts, MCP capabilities, and forbidden behaviors.

## Host Integration Flow

External agents should treat the skill pack manifest as the entrypoint:

```python
from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.schemas.skill import SkillInput
from src.tools.evidence.validators import compile_evidence_graph
from src.skills_runtime.decision_support import DecisionSupportSkill

manifest = load_skillpack_manifest("skillpack/fund-agent.skillpack.yaml")

news_spec = manifest.skill("news_research")
news_skill_cls = resolve_runtime(news_spec.runtime)
news_skill = news_skill_cls(mcp_adapter=host_mcp)

news_output = news_skill.run(
    SkillInput(
        task_id="host-task-1",
        step_id="news-1",
        skill_name="news_research",
        payload={"query": "fund:110011"},
        required_mcp_capabilities=news_spec.requires_mcp,
    )
)

compile_result = compile_evidence_graph(news_output.evidence_items)

decision_output = DecisionSupportSkill().run(
    SkillInput(
        task_id="host-task-1",
        step_id="decision-1",
        skill_name="decision_support",
        payload={
            "evidence_graph": compile_result.graph.to_dict(),
            "objective": "review fund",
            "time_horizon": "1 year",
        },
    )
)
```

The host can freely choose a different order, skip skills, add its own planner,
or combine `fund-agent` tools with other skill packs.

## Runtime Skills

| Skill | Runtime | Produces | MCP |
|---|---|---|---|
| `fund_analysis` | `src.skills_runtime.fund_analysis:FundAnalysisSkill` | `HardEvidence`, portfolio artifacts | none |
| `news_research` | `src.skills_runtime.news_research:NewsResearchSkill` | `SoftEvidence` | `web_search`, `financial_news` |
| `sentiment_analysis` | `src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill` | `SoftEvidence` | `social_sentiment` |
| `thesis_generation` | `src.skills_runtime.thesis_generation:ThesisGenerationSkill` | `ThesisDraft` artifact | none |
| `decision_support` | `src.skills_runtime.decision_support:DecisionSupportSkill` | `Decision`, `ExecutionLedger` | none |

Only `decision_support` may produce formal `Decision` and `ExecutionLedger`
artifacts. Other skills return evidence, draft artifacts, warnings, and
structured errors through `SkillOutput`.

## MCP Boundary

MCP providers are injected by the external host. This repository does not
hardcode Tavily, Finnhub, Exa, Firecrawl, Reddit, or other vendor SDKs in the
skill runtime.

`src.tools.adapters.mcp` defines:

- `MCPCapability`
- `MCPHostAdapter`
- `InMemoryMCPHostAdapter` for tests/examples

News and sentiment skills may call `mcp_adapter.call(...)`; no skill should
make direct network requests.

## Contracts And Tools

- `SkillInput` / `SkillOutput`: `src.schemas.skill`
- `EvidenceItem`: `src.schemas.evidence`
- `EvidenceGraph`: `src.schemas.evidence_graph`
- `Decision` / `ExecutionLedger`: `src.schemas.decision`
- Fund and portfolio schemas: `src.schemas.fund`
- Fund metrics: `src.tools.fund.metrics`
- Portfolio analysis: `src.tools.portfolio.analysis`
- Evidence compiler: `src.tools.evidence.validators.compile_evidence_graph`
- Evidence review helper: `src.tools.evidence.review.review_evidence_graph`
- Evidence builders: `src.tools.evidence.builders`
- KnowledgeGraph queries: `src.graph`

Active decisions (`BUY`, `SELL`, `INCREASE`, `REDUCE`) must anchor to real
EvidenceGraph evidence IDs. Passive decisions (`WAIT`, `HOLD`, `PAUSE_DCA`) may
have empty anchors only when insufficient evidence or review blockage is
explicitly recorded.

## Repository Layout

```text
skillpack/                  # manifest, capabilities, tool and contract declarations
skills/                     # host-readable Skill instructions and references
src/
  skills_runtime/           # host-callable runtime skill handlers
  skillpack/                # manifest loader, resolver, validator
  schemas/                  # typed contracts
  tools/                    # pure tools and MCP adapter boundary
  graph/                    # KnowledgeGraph implementation
  infra/                    # config/data/persistence/vectorstore implementation
  core/                     # optional reference helpers, not host entrypoint
  workflows/                # optional reference wrappers, not host entrypoint
legacy/README.md            # pointer to v0.1.0-skillpack-alpha legacy archive
examples/reference_workflows/
docs/
```

## Reference Workflows

`src.core.research_os` and `src.workflows.research_os` are deprecated
reference-only modules retained for compatibility and examples. They are not
required by the skill pack manifest, not required by host integration, and not
the recommended product entrypoint.

## Archive Note

Legacy code (CLI, news pipeline, scoring, strategy, reports, UI) was removed
after `v0.1.0-skillpack-alpha`. To inspect the old implementation:

```bash
git checkout v0.1.0-skillpack-alpha
```

See `docs/archive/legacy-system.md` for details.

## Agent Quick Start

1. Read `AGENTS.md` — coding agent integration guide.
2. Read `skillpack/fund-agent.skillpack.yaml` — plugin manifest.
3. Use `docs/agent-host-quickstart.md` — host integration quickstart.
4. Run `python examples/minimal_host_news_to_decision.py` — news-to-decision demo.
5. Run `python examples/minimal_host_portfolio_review.py` — portfolio review demo.
6. Run `bash scripts/check_plugin_gate.sh` — verify all gates pass.

## Development

```bash
PYTHONPATH=. python -m compileall src tests
PYTHONPATH=. pytest -q
```

Provider credentials are host concerns. The skill pack itself only declares MCP
capabilities and contracts.

## License

MIT
