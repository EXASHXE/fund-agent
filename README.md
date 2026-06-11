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

**[START HERE →](docs/START_HERE.md)** — one-page quickstart for hosts and coding agents.

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
For fake personal fund bridge fixtures, see
[`examples/scenarios/README.md`](examples/scenarios/README.md).
For fund-analysis golden regression snapshots used before internal refactors,
see [`tests/golden/README.md`](tests/golden/README.md).

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
they are optional examples only and are not host integration entrypoints.
Host integrations do not need to import or call historical autonomous runtime modules.

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
legacy/README.md            # pointer to v0.1.0-skillpack-alpha legacy archive
examples/reference_workflows/
docs/
```

## Reference Workflows

Historical autonomous runtime surfaces were removed from the current source
tree. Reference workflow examples under `examples/reference_workflows/` are
optional examples only; the manifest and runtime bridge remain the host-facing
entrypoints.

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
flow. Source-checkout runtime execution requires Python 3.11+.
The source-checkout runtime bridge path is:
`python scripts/run_skill.py --list-skills --pretty`.

- OpenCode (project-local plugin, metadata + doc-reader only):
  [`.opencode/INSTALL.md`](.opencode/INSTALL.md) /
  [`docs/install/opencode.md`](docs/install/opencode.md)
- Manual / Python host: [`docs/install/manual-host.md`](docs/install/manual-host.md)
- Runtime bridge CLI (thin JSON-in / JSON-out Python shim,
  host-agnostic): [`docs/install/runtime-bridge-cli.md`](docs/install/runtime-bridge-cli.md)
- Codex (manual / light): [`docs/install/codex.md`](docs/install/codex.md)
- Other harnesses: see [`docs/host-compatibility.md`](docs/host-compatibility.md)
- OpenCode troubleshooting: [`docs/install/opencode-troubleshooting.md`](docs/install/opencode-troubleshooting.md)
- v1.2 host integration checklist: [`docs/v1.2-host-integration-checklist.md`](docs/v1.2-host-integration-checklist.md)
- Deeper runtime bridge design (subprocess handlers, OpenCode
  plugin tool wrapper — still future):
  [`docs/design/runtime-bridge.md`](docs/design/runtime-bridge.md)

### Supported execution modes

**Mode A — source checkout runtime bridge:**
- `python scripts/run_skill.py ...` (canonical)
- `fund-agent-run-skill ...` (console script, available after `pip install -e .`)
- `python -m src.skillpack.run_skill ...` (module invocation)
- Host invokes a local subprocess; host owns data fetching/MCP/provider SDKs

**Mode B — Python editable install:**
- `pip install -e .`
- Runtime bridge still reads source checkout skillpack/docs/contracts
- Wheel-only install is not yet tested; source checkout is required

**Mode C — OpenCode plugin:**
- Metadata + doc-reader only
- Does not invoke Python, does not run fund_analysis, does not include provider SDKs
- The runtime bridge is a separate, independent surface

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

## v1 Artifacts

### fund_analysis artifacts (never emits Decision/ExecutionLedger)

| Artifact | Category | Required |
|---|---|---|
| `portfolio_summary` | core_portfolio | yes |
| `position_summary` | core_portfolio | yes |
| `pnl_summary` | ledger_and_pnl | yes |
| `exposure_summary` | exposure_and_risk | yes |
| `risk_flags` | exposure_and_risk | yes |
| `warnings` | core | yes |
| `fund_analysis_report` | core | yes |
| `report_sections` | report_output | yes |
| `report_outline` | report_output | yes |
| `report_quality_gate` | report_output | yes |
| `data_completeness` | report_output | yes |
| `analysis_coverage` | report_output | yes |
| `report_limitations` | report_output | yes |
| `analysis_plan` | diagnostics | yes |
| `evidence_gap_diagnostics` | diagnostics | yes |
| `position_contribution` | diagnostics | yes |
| `profit_protection_diagnostics` | diagnostics | conditional |
| `redemption_fee_risk` | diagnostics | conditional |
| `benchmark_divergence_diagnostics` | diagnostics | conditional |
| `right_side_confirmation_diagnostics` | diagnostics | conditional |
| `event_hype_failure_diagnostics` | diagnostics | conditional |
| `cash_deployment_diagnostics` | diagnostics | conditional |

### decision_support artifacts (only formal Decision/ExecutionLedger producer)

| Artifact | Description |
|---|---|
| `decision` | Single formal Decision with reason_codes, blocked_by, evidence_state |
| `decisions` | Trade-plan mode: list of formal Decisions |
| `execution_ledger` | ExecutionLedger wrapping all decisions |
| `decision_status` | Top-level action string |
| `decision_count` | Number of decisions |
| `audit_trail` | Combined audit entries |
| `warnings` | Pipeline warnings |

## Data Boundary

Core runtime is deterministic, local-only, and provider-agnostic:
- No network calls
- No API keys
- No provider SDK imports (OpenAI, Anthropic, Tavily, Exa, Firecrawl, Finnhub, AkShare, LangChain, broker APIs)
- No broker/order execution
- No autonomous planner loops

The external host owns credentials, live data providers, MCP implementations, and final UX.

## v1.1 Reliability and Explainability

v1.1 hardens the decision pipeline with improved diagnostics, KnowledgeGraph
integration, and explainability artifacts:

- **KnowledgeGraph hardening** — enum-safe queries via `KGEdgeType` comparison
  in `src/graph/queries.py`. The KnowledgeGraph provides structural
  entity/relationship context (sectors, themes, overlap) as an optional
  enrichment layer for portfolio analysis.
- **`knowledge_graph_summary`** — optional `fund_analysis` artifact emitted
  when holdings data supports it. Provides KG-derived context for reports.
  Omitted (`enabled=false`) when data is insufficient.
- **`evidence_anchor_diagnostics`** — `decision_support` artifact that
  explains anchor validity and coverage per decision and per trade.
- **`risk_constraint_conflicts`** — `decision_support` artifact that
  explains budget/constraint blocking with cap/downgrade details.
- **`ledger_summary`** — new field in `ExecutionLedger` providing a
  deterministic summary of all decisions, total execution amounts, and
  passive/active action counts.

### KnowledgeGraph vs EvidenceGraph

- **KnowledgeGraph** (`src/graph/`) — structural entity/relationship context
  for portfolio analysis (sectors, themes, cross-fund overlap). Optional
  enrichment layer consumed by `fund_analysis`.
- **EvidenceGraph** (`src/schemas/evidence_graph`) — evidence layer consumed
  by `decision_support` for formal decision gatekeeping. Tracks evidence
  items, edges, and stats. Remains the sole evidence layer for formal
  `Decision` / `ExecutionLedger` production.

### Host-injected MCP boundary

MCP providers are always host-injected via `MCPHostAdapter`. The dev-only
MCP harness (`tools/dev/mcp_harness/`) provides fake responses for testing
and handles `financial_news`, `web_search`, and `social_sentiment`
capability types in fake mode only. Live mode is env-gated and not
implemented. No skill makes direct network requests.

## Test Gates

```bash
PYTHONPATH=. pytest -q
bash scripts/check_plugin_gate.sh
PYTHONPATH=. pytest tests/architecture -q
PYTHONPATH=. pytest tests/contracts -q
PYTHONPATH=. pytest tests/install -q
```

## Release Readiness Status

See [docs/v1-release-readiness.md](docs/v1-release-readiness.md) for the full v1 release checklist.

## License

MIT
