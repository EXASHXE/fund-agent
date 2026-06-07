# fund-agent: Host-Agnostic AI Financial Research Skill Pack

> Host-Agnostic AI Financial Research Skill Pack / Agent Plugin.

`fund-agent` is a discoverable skill pack for external agent hosts such as
OpenCode, Claude Code, Codex, OpenClaw, Hermes, and similar runtimes. The host
agent owns planning and orchestration. This repository provides callable
financial research skills, typed contracts, evidence tools, KnowledgeGraph
helpers, and a host-native MCP adapter boundary.

At the skill layer, `fund-agent` is Markdown-first: `skills/<slug>/SKILL.md`
files are the primary agent-facing instructions, and `references/*.md` files
hold longer policy, examples, templates, and methods. Python under `src/`
remains deterministic runtime, schema, and tool support.

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
- `skillpack/input-contracts.yaml`: machine-readable `fund_analysis` input contract
- `skillpack/artifact-contracts.yaml`: machine-readable `fund_analysis` artifact contract
- `skills/README.md`: Markdown-first skill directory policy
- `skills/SKILL.md`: host-readable skill pack index
- `skills/<slug>/SKILL.md`: primary agent-facing skill instructions
- `skills/<slug>/references/*.md`: longer policy and templates
- `src/skills_runtime/`: host-callable Python skill handlers
- `src/tools/`: pure fund, portfolio, quant, ledger, evidence, and adapter tools
- `src/schemas/`: typed contracts for skill, fund, evidence, graph, decision, ledger
- `src/graph/`: KnowledgeGraph implementation and query helpers
- `src/tools/adapters/mcp.py`: host-native MCP adapter abstraction

For host-specific integration recipes, see
[`docs/host-integrations/README.md`](docs/host-integrations/README.md).

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

External hosts must read the manifest for skill discovery. Do not infer runtime
skill IDs from folder names. For example, `fund_analysis` is the runtime skill
ID and `fund-analysis` is the canonical Markdown doc slug.

## Skill Surface (Superpowers-compatible)

`fund-agent` exposes a **composable collection of Markdown skills**, the same
shape as a Superpowers / OpenCode Agent Skills / Codex Skills pack: one
hyphenated `SKILL.md` directory per skill, with the directory name matching
the skill's frontmatter `name` field. The agent-facing skill name is always
the hyphenated slug; the underscore name is the Python runtime ID only.

- **Primary / default skill:** `fund-analysis`. For ordinary portfolio and
  fund report requests (for example
  `分析下我的基金给出报告`), load `fund-analysis` first. It alone is
  sufficient for report-only flows.
- **Supporting skills:** `decision-support`, `news-research`,
  `sentiment-analysis`, `thesis-generation`. Load one of these only when
  the subtask description matches, and only after `fund-analysis` (or
  equivalent evidence) is in scope.
- **Python runtime IDs** remain underscore names in the manifest and in
  Python: `fund_analysis`, `decision_support`, `news_research`,
  `sentiment_analysis`, `thesis_generation`. External hosts should use
  these for actual `skill.run(SkillInput)` calls.
- **Discovery** is always `skillpack/fund-agent.skillpack.yaml`; the
  `skills/<slug>/SKILL.md` files are the agent-facing policy layer.

The legacy `fund-analyst` persona material is archived under
`docs/archive/fund-analyst/`; it is not installed, not discovered, and
not a runtime entrypoint. Underscore `skills/` directories are no
longer present; any directory whose name contains `_` is not part of
the agent-facing surface.

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

| Runtime skill ID (Python) | Agent-facing slug | Role | Produces | MCP |
|---|---|---|---|---|
| `fund_analysis` | `fund-analysis` | **primary / default** | `HardEvidence`, portfolio artifacts | none |
| `decision_support` | `decision-support` | supporting | `Decision`, `ExecutionLedger` | none |
| `news_research` | `news-research` | supporting | `SoftEvidence` | `web_search`, `financial_news` |
| `sentiment_analysis` | `sentiment-analysis` | supporting | `SoftEvidence` | `social_sentiment` |
| `thesis_generation` | `thesis-generation` | supporting | `ThesisDraft` artifact | none |

- The **agent-facing skill name** is the hyphenated slug
  (`fund-analysis`, `decision-support`, …). Hosts should pass that slug
  to the OpenCode plugin's `fund_agent_skill_doc` tool.
- The **Python runtime ID** is the underscore name in the manifest
  (`fund_analysis`, `decision_support`, …). Hosts should pass that to
  `fund_agent_runtime_hint` and to `SkillInput(skill_name=...)`.
- The two are linked 1:1 by the manifest; do not infer either from a
  filesystem directory name alone.

Only `decision_support` may produce formal `Decision` and `ExecutionLedger`
artifacts. Other skills return evidence, draft artifacts, warnings, and
structured errors through `SkillOutput`.

`fund-analysis` is the recommended starting point for ordinary user
requests like `分析下我的基金给出报告`. Supporting skills should be
loaded only when their description matches the subtask. See
`skills/fund-analysis/SKILL.md` for the "When to load supporting skills"
table.

`fund-analyst` is legacy/reference-only persona material archived under
`docs/archive/fund-analyst/`. It is not installed, not discovered, and
not a runtime entrypoint.

## MCP Boundary

MCP providers are injected by the external host. This repository does not
hardcode Tavily, Finnhub, Exa, Firecrawl, Reddit, AkShare, OpenAI, Anthropic,
LangChain, or other vendor SDKs in the skill runtime.

`src.tools.adapters.mcp` defines:

- `MCPCapability`
- `MCPHostAdapter`
- `InMemoryMCPHostAdapter` for tests/examples

News and sentiment skills may call `mcp_adapter.call(...)`; no skill should
make direct network requests.

## Contracts And Tools

- `SkillInput` / `SkillOutput`: `src.schemas.skill`
- Fund analysis input contract: `docs/contracts/fund-analysis-input-contract.v1.md`
- Fund analysis artifact contract: `docs/contracts/fund-analysis-artifacts.v1.md`
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
  README.md                 # directory naming and Markdown-first policy
  fund-analysis/            # canonical docs for runtime ID fund_analysis
  decision-support/         # canonical docs for runtime ID decision_support
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
3. Read `skills/README.md` and the relevant `skills/<slug>/SKILL.md`.
4. Use `docs/agent-host-quickstart.md` — host integration quickstart.
5. Use `docs/workflows/personal-fund-report.md` for personal fund reports.
6. Run `python examples/minimal_host_news_to_decision.py` — news-to-decision demo.
7. Run `python examples/minimal_host_portfolio_review.py` — portfolio review demo.
8. Run `bash scripts/check_plugin_gate.sh` — verify all gates pass.

## Personal Fund Reports

`fund_analysis` now produces deterministic, host-displayable report artifacts:
`report_sections`, `report_outline`, and `report_quality_gate`, alongside
`data_completeness`, `analysis_coverage`, and `report_limitations`. Hosts can
render these structured sections directly or adapt them to their final UX.

Missing benchmark, peer, manager, factor, fee, or redemption data produces
`PARTIAL` or `MISSING` report sections and limitations. The composer does not
fabricate absent comparisons, rankings, manager stability, fee warnings, or
liquidity facts. Formal actions still require `DecisionSupportSkill`.

## Install

`fund-agent` is host-agnostic. The first native install target is
**OpenCode**; the canonical install for any Python host is the manual
flow.

- OpenCode (project-local plugin, metadata + docs only):
  [`.opencode/INSTALL.md`](.opencode/INSTALL.md) /
  [`docs/install/opencode.md`](docs/install/opencode.md)
- Manual / Python host: [`docs/install/manual-host.md`](docs/install/manual-host.md)
- Runtime bridge CLI (thin JSON-in / JSON-out Python shim,
  host-agnostic): [`docs/install/runtime-bridge-cli.md`](docs/install/runtime-bridge-cli.md)
- Codex (manual / light): [`docs/install/codex.md`](docs/install/codex.md)
- Other harnesses: see [`docs/host-compatibility.md`](docs/host-compatibility.md)
- Deeper runtime bridge design (subprocess handlers, OpenCode
  plugin tool wrapper — still future):
  [`docs/design/runtime-bridge.md`](docs/design/runtime-bridge.md)

The OpenCode plugin exposes a `fund_agent_skills` tool, a
`fund_agent_skill_doc` tool, and a `fund_agent_runtime_hint` tool. It
does not run an autonomous loop, does not fetch data, and does not
place trades. The host agent owns planning, MCP provider wiring, and
final user interaction.

The runtime bridge CLI is a separate, independent surface for hosts
that want a process boundary. It is **not** wired into the OpenCode
plugin; the plugin still does not call Python.

## Development

```bash
PYTHONPATH=. python -m compileall src tests
PYTHONPATH=. pytest -q
bash scripts/check_plugin_gate.sh
```

`scripts/check_plugin_gate.sh` auto-installs only `pytest` and `pyyaml`
(via `pip install --quiet pytest pyyaml`) if they are missing on the
host, so a fresh `pip install`-less environment can still run the
gate. The script does not install any other dependency and does not
mutate the project requirements.

Provider credentials are host concerns. The skill pack itself only declares MCP
capabilities and contracts.

## License

MIT
