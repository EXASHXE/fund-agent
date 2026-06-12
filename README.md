# fund-agent: Host-Agnostic Mutual Fund Advisory Skill Pack

> Host-Agnostic Mutual Fund Advisory Skill Pack / Agent Plugin.

`fund-agent` is a discoverable skill pack for external agent hosts such as
OpenCode, Claude Code, Codex, OpenClaw, Hermes, and similar runtimes. The host
agent owns planning and orchestration. This repository provides callable
financial research skills, typed contracts, evidence tools, KnowledgeGraph
helpers, and a host-native MCP adapter boundary.

At the skill layer, `fund-agent` is Markdown-first: `skills/<slug>/SKILL.md`
files are the primary agent-facing instructions, and `references/*.md` files
hold longer policy, examples, templates, and methods. Python under `src/`
remains deterministic runtime, schema, and tool support.

## What fund-agent Is

A **host-agnostic skill pack for personal mutual fund advisory workflows**:

- Deterministic local runtime for fund analysis, decision support, and evidence graph
- Typed contracts, evidence tools, KnowledgeGraph helpers
- External agent/host owns orchestration and live data
- Designed for: `fund_analysis`, `decision_support`, `EvidenceGraph`, final report, quality gate, workflow trace, and personal regression

## What fund-agent Is Not

- **Not a broker** — no order execution, no trade placement
- **Not an autonomous trader** — no agent loops, no self-directed trading
- **Not a live-data provider in core** — no network calls, no provider SDKs in runtime
- **Not an LLM report generator** — deterministic composition only
- **Not a stock-picking social persona agent** — no social features, no recommendations without evidence
- **Not guaranteed real-time market data** — provider adapters are optional prototypes

## 30-Second Start

```bash
# Check readiness
fund-agent doctor --pretty

# Run a sample skill
fund-agent run-skill --skill fund_analysis --input examples/runtime_bridge_fund_analysis_input.json --pretty

# Run personal regressions
fund-agent regressions --pretty

# Run a specific scenario with trace
fund-agent regressions --scenario mixed_portfolio_report_only_zh --show-trace

# Run project audit
fund-agent audit --pretty

# Standalone regression script
python scripts/run_personal_regressions.py --pretty

# Smoke host install
python scripts/smoke_host_install.py
```

## Core Workflow

```
fund_analysis → EvidenceGraph bridge → optional decision_support → final report → quality gate / workflow trace
```

- **Report-only** flows use `fund_analysis` alone and do **not** call `decision_support`
- **Formal trade** requests may call `decision_support` which creates audit artifacts only
- `suggested_rebalance_plan` remains analysis-only and is not a trade instruction
- No broker execution

## Report-Only vs Formal Decision

| Flow | Calls decision_support? | Produces |
|------|------------------------|----------|
| Report-only (`REPORT_ONLY`, `SOFT_ACTION_ADVICE`) | No | `report_sections`, `report_outline`, `report_quality_gate` |
| Formal trade (`FORMAL_TRADE_DECISION`) | Yes | `Decision`, `ExecutionLedger`, `audit_trail` |

SOFT_ACTION_ADVICE alone must not force decision_support.

## Provider Boundary

- **Core runtime is no-network** — no provider SDK imports, no API calls
- **Provider contracts** live under `src/host_data/` (no adapters, no network)
- **Host adapter examples** live under `examples/host_data_adapters/`
- **AkShare** is an optional fallback/prototype adapter (not core)
- **Eastmoney and Xueqiu** are optional prototype adapters and not fully supported production connectors
- **Credentials** via config/env only — no secrets committed
- **News MCP/API keys** are host-owned — core never handles them

## Public API

Stable import paths for external consumers:

```python
from fund_agent.workflow import WorkflowTrace, classify_advisory_intent, compose_advisory_workflow_report
from fund_agent.regression import list_personal_regression_fixtures, run_personal_regression_fixture
from fund_agent.quality import evaluate_advisory_quality_gate, FORBIDDEN_EXECUTION_FIELDS
from fund_agent.providers import ProviderCapability, ProviderConfig, ProviderRegistry, ProviderResult
from fund_agent.reporting import compose_advisory_workflow_report, compute_report_status
from fund_agent.runtime import FundAnalysisSkill, DecisionSupportSkill, SkillInput, SkillOutput
from fund_agent.version import __version__
from fund_agent.cli import build_parser, main
```

The `fund_agent.*` paths are the **preferred public API**. Deep import paths
(`src.skills_runtime.workflow`, `src.host_data`, etc.) remain functional for
backward compatibility but are internal implementation details.

## CLI

```bash
fund-agent doctor [--pretty] [--json]           # deterministic readiness check
fund-agent run-skill --skill ID --input PATH    # run a manifest skill
fund-agent regressions [--pretty] [--scenario]  # run personal regression fixtures
fund-agent provider-smoke [--provider NAME]     # optional adapter smoke test (opt-in)
fund-agent audit [--pretty] [--json]            # run project audit scripts
```

Old commands remain compatible: `fund-agent-run-skill`, `fund-agent-doctor`.

## v0.9.0 Pre-launch Baseline

This is **fund-agent v0.9.0**, the first pre-launch baseline. Provider adapters
(AkShare, Eastmoney, Xueqiu) are prototypes unless smoke-tested with real
credentials. The v0.9.0 tag has not been created yet.

See [`docs/release/v0.9.0-readiness-checklist.md`](docs/release/v0.9.0-readiness-checklist.md).

## Skill Pack Manifest

The standard plugin entrypoint is
`skillpack/fund-agent.skillpack.yaml`. It declares runtime classes, schemas,
contracts, MCP capabilities, and forbidden behaviors.

External hosts must read the manifest for skill discovery. Do not infer runtime
skill IDs from folder names. For example, `fund_analysis` is the runtime skill
ID and `fund-analysis` is the canonical Markdown doc slug.

## Runtime Skills

| Runtime skill ID (Python) | Agent-facing slug | Role | Produces | MCP |
|---|---|---|---|---|
| `fund_analysis` | `fund-analysis` | **primary / default** | `HardEvidence`, portfolio artifacts | none |
| `decision_support` | `decision-support` | supporting | `Decision`, `ExecutionLedger` | none |
| `news_research` | `news-research` | supporting | `SoftEvidence` | `web_search`, `financial_news` |
| `sentiment_analysis` | `sentiment-analysis` | supporting | `SoftEvidence` | `social_sentiment` |
| `thesis_generation` | `thesis-generation` | supporting | `ThesisDraft` artifact | none |

Only `decision_support` may produce formal `Decision` and `ExecutionLedger`
artifacts. Other skills return evidence, draft artifacts, warnings, and
structured errors through `SkillOutput`.

`fund_analysis` is the recommended starting point for ordinary user
requests like `分析下我的基金给出报告`. Supporting skills should be
loaded only when their description matches the subtask. See
`skills/fund-analysis/SKILL.md` for the "When to load supporting skills"
table.

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

## Repository Layout

```text
skillpack/                  # manifest, capabilities, tool and contract declarations
skills/                     # host-readable Skill instructions and references
  README.md                 # directory naming and Markdown-first policy
  fund-analysis/            # canonical docs for runtime ID fund_analysis
  decision-support/         # canonical docs for runtime ID decision_support
fund_agent/                 # top-level public API shim (preferred import path)
src/
  fund_agent/               # public facade implementation (workflow, regression, quality, providers, reporting, runtime, cli)
  skills_runtime/           # host-callable runtime skill handlers
  skillpack/                # manifest loader, resolver, validator
  schemas/                  # typed contracts
  tools/                    # pure tools and MCP adapter boundary
  graph/                    # KnowledgeGraph implementation
  host_data/                # provider contracts and registry (no adapters, no network)
scripts/
  audit/                    # project audit scripts
  run_skill.py              # thin wrapper around runtime bridge
  run_personal_regressions.py
  fund_agent_doctor.py
examples/
  host_data_adapters/       # optional host adapter prototypes (AkShare, Eastmoney, Xueqiu)
  personal_portfolio_regressions/
  scenarios/
legacy/README.md            # pointer to v0.1.0-skillpack-alpha legacy archive
docs/
```

## Personal Fund Reports

`fund_analysis` produces deterministic, host-displayable report artifacts:
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

- OpenCode (project-local plugin, metadata + doc-reader only):
  [`.opencode/INSTALL.md`](.opencode/INSTALL.md) /
  [`docs/install/opencode.md`](docs/install/opencode.md)
- Manual / Python host: [`docs/install/manual-host.md`](docs/install/manual-host.md)
- Runtime bridge CLI: [`docs/install/runtime-bridge-cli.md`](docs/install/runtime-bridge-cli.md)
- Codex (manual / light): [`docs/install/codex.md`](docs/install/codex.md)

### Supported execution modes

**Mode A — source checkout runtime bridge:**
- `python scripts/run_skill.py ...` (canonical)
- `fund-agent-run-skill ...` (console script, available after `pip install -e .`)
- Host invokes a local subprocess; host owns data fetching/MCP/provider SDKs

**Mode B — Python editable install:**
- `pip install -e .`
- Runtime bridge still reads source checkout skillpack/docs/contracts
- Wheel-only install is not yet tested; source checkout is required

**Mode C — OpenCode plugin:**
- Metadata + doc-reader only
- Does not invoke Python, does not run fund_analysis, does not include provider SDKs
- The runtime bridge is a separate, independent surface

## Contracts And Tools

- `SkillInput` / `SkillOutput`: `src.schemas.skill`
- Fund analysis input contract: `docs/contracts/fund-analysis-input-contract.v1.md`
- Fund analysis artifact contract: `docs/contracts/fund-analysis-artifacts-contract.v1.md`
- `EvidenceItem`: `src.schemas.evidence`
- `EvidenceGraph`: `src.schemas.evidence_graph`
- `Decision` / `ExecutionLedger`: `src.schemas.decision`
- Fund and portfolio schemas: `src.schemas.fund`
- Fund metrics: `src.tools.fund.metrics`
- Portfolio analysis: `src.tools.portfolio.analysis`
- Evidence compiler: `src.tools.evidence.validators.compile_evidence_graph`
- KnowledgeGraph queries: `src.graph`

Active decisions (`BUY`, `SELL`, `INCREASE`, `REDUCE`) must anchor to real
EvidenceGraph evidence IDs. Passive decisions (`WAIT`, `HOLD`, `PAUSE_DCA`) may
have empty anchors only when insufficient evidence or review blockage is
explicitly recorded.

## Data Boundary

Core runtime is deterministic, local-only, and provider-agnostic:
- No network calls
- No API keys
- No provider SDK imports (OpenAI, Anthropic, Tavily, Exa, Firecrawl, Finnhub, AkShare, LangChain, broker APIs)
- No broker/order execution
- No autonomous agent loops

The external host owns credentials, live data providers, MCP implementations, and final UX.

## Reliability and Explainability

v1.1 hardens the decision pipeline with improved diagnostics, KnowledgeGraph
integration, and explainability artifacts:

- **KnowledgeGraph hardening** — enum-safe queries via `KGEdgeType` comparison
  in `src/graph/queries.py`. The KnowledgeGraph provides structural
  entity/relationship context (sectors, themes, overlap) as an optional
  enrichment layer for portfolio analysis.
- **`knowledge_graph_summary`** — optional `fund_analysis` artifact emitted
  when holdings data supports it. Provides KG-derived context for reports.
- **`evidence_anchor_diagnostics`** — `decision_support` artifact that
  explains anchor validity and coverage per decision and per trade.
- **`risk_constraint_conflicts`** — `decision_support` artifact that
  explains budget/constraint blocking with cap/downgrade details.
- **`ledger_summary`** — field in `ExecutionLedger` providing a
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

## Test Gates

```bash
PYTHONPATH=. pytest -q
bash scripts/check_plugin_gate.sh
PYTHONPATH=. pytest tests/architecture -q
PYTHONPATH=. pytest tests/contracts -q
PYTHONPATH=. pytest tests/install -q
```

## Development

For the coding agent integration guide, see [`AGENTS.md`](AGENTS.md).

```bash
PYTHONPATH=. python -m compileall src tests
PYTHONPATH=. pytest -q
bash scripts/check_plugin_gate.sh
```

Provider credentials are host concerns. The skill pack itself only declares MCP
capabilities and contracts.

## Archive Note

Legacy code (CLI, news pipeline, scoring, strategy, reports, UI) was removed
after `v0.1.0-skillpack-alpha`. To inspect the old implementation:

```bash
git checkout v0.1.0-skillpack-alpha
```

See `docs/archive/legacy-system.md` for details.

## License

MIT
