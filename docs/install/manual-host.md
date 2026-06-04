# Manual Host Install

This document is the **canonical install path** for `fund-agent` as a
host-agnostic Python skill pack. It works for any Python host: a
custom CLI, a Jupyter notebook, a service that wants to embed
`fund-agent`, Claude Code, OpenClaw, Hermes, or any agent that can
import Python packages.

If you are specifically targeting **OpenCode**, prefer
[`docs/install/opencode.md`](./opencode.md) for the project-local
plugin install.

If you are targeting **Codex**, see
[`docs/install/codex.md`](./codex.md).

## What this install actually gives you

After the manual install you can:

- Load `skillpack/fund-agent.skillpack.yaml` to discover the five
  manifest runtime skills.
- Resolve any manifest runtime class via
  `src.skillpack.loader.resolve_runtime(...)`.
- Build a `SkillInput`, inject an `MCPHostAdapter` for skills that need
  MCP data, and call `skill.run(input)`.
- Call `compile_evidence_graph(...)` to consolidate evidence.
- Call `DecisionSupportSkill` to produce a formal `Decision` and
  `ExecutionLedger`.

The five manifest runtime skills are:

| Runtime ID | Doc slug | Python runtime class | Produces |
|---|---|---|---|
| `fund_analysis` | `fund-analysis` | `src.skills_runtime.fund_analysis:FundAnalysisSkill` | `HardEvidence`, fund analysis report |
| `news_research` | `news-research` | `src.skills_runtime.news_research:NewsResearchSkill` | `SoftEvidence` |
| `sentiment_analysis` | `sentiment-analysis` | `src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill` | `SoftEvidence` |
| `thesis_generation` | `thesis-generation` | `src.skills_runtime.thesis_generation:ThesisGenerationSkill` | `ThesisDraft` artifact |
| `decision_support` | `decision-support` | `src.skills_runtime.decision_support:DecisionSupportSkill` | `Decision`, `ExecutionLedger` |

You will **not** get:

- An autonomous planner loop. The host owns that.
- Provider SDKs. The host injects provider implementations through
  `MCPHostAdapter`.
- A ready-made CLI command. The host wraps the runtime as it sees fit.

## Prerequisites

- Python 3.11 or newer
- `git`
- A POSIX shell (Linux / macOS) or Git Bash / WSL on Windows
- Optional: a virtualenv tool such as `venv` or `uv`

## Install

```bash
# 1. Clone the repo
git clone https://github.com/EXASHXE/fund-agent.git
cd fund-agent

# 2. (Recommended) Create a virtualenv
python -m venv .venv
source .venv/bin/activate     # Linux / macOS
# .venv\Scripts\activate      # Windows PowerShell

# 3. Install in editable mode (minimal — no provider SDKs)
pip install -e .

# 4. (Optional) Install dev / test dependencies
pip install -r requirements-dev.txt

# 5. (Optional) Install local analysis helpers for demos
pip install -r requirements-optional.txt
```

## Verify

```bash
# Run the canonical plugin gate
bash scripts/check_plugin_gate.sh

# Run the news-to-decision demo
python examples/minimal_host_news_to_decision.py

# Run the portfolio review demo
python examples/minimal_host_portfolio_review.py

# Run the trade-plan-to-decisions demo
python examples/minimal_host_trade_plan_to_decisions.py
```

Each demo prints a JSON document to stdout. If they all print valid
JSON and exit 0, the install is good.

## What the host loads

A host integration is responsible for four things:

1. **Manifest discovery.** Read
   `skillpack/fund-agent.skillpack.yaml` to learn the manifest skill
   IDs, runtime classes, required MCP capabilities, and forbidden
   behaviors.

   ```python
   from src.skillpack.loader import load_skillpack_manifest
   manifest = load_skillpack_manifest("skillpack/fund-agent.skillpack.yaml")
   ```

2. **Skill doc reading.** For each manifest skill ID, read
   `skills/<slug>/SKILL.md` (where `<slug>` is the hyphenated
   documentation slug, e.g. `fund-analysis`) for agent-facing
   workflow, policy, and report style. The runtime ID
   `fund_analysis` maps to the doc slug `fund-analysis`; see
   `skills/README.md` for the full mapping.

3. **Runtime resolution.** Use
   `src.skillpack.loader.resolve_runtime(runtime_path)` to import the
   Python class. The manifest's `runtime` field is the canonical
   pointer; do not infer it from folder names.

4. **Skill invocation.** Construct a `SkillInput`, inject an
   `MCPHostAdapter` if needed, and call `skill.run(input)`. Collect
   `SkillOutput.evidence_items`, `artifacts`, `warnings`, and
   `errors`. Call `compile_evidence_graph` if the host wants to
   consolidate evidence. Call `DecisionSupportSkill` when the host
   wants a formal `Decision` and `ExecutionLedger`.

## Passing host-owned data

`fund-agent` is **not** an autonomous agent runtime and does not fetch
NAV, holdings, news, or sentiment. The host must provide those.

For `fund_analysis` the host passes portfolio, NAV history, fund
holdings, risk profile, and constraints through `SkillInput.payload`.
For `news_research` the host provides an `MCPHostAdapter` that knows
how to call `web_search` and `financial_news`. For
`sentiment_analysis` the host provides an `MCPHostAdapter` that knows
how to call `social_sentiment`.

A reference `MCPHostAdapter` for tests and demos is
`src.tools.adapters.mcp.InMemoryMCPHostAdapter`. Real hosts wire
their own implementation.

## Decision support

`DecisionSupportSkill` is the **only** skill that may produce a
formal `Decision` and `ExecutionLedger`. It accepts an
`EvidenceGraph` (built from the host's evidence items) and an
optional `portfolio_context`, `risk_profile`, `constraints`, and
`target_trade_amount`. Active actions (`BUY`, `SELL`, `INCREASE`,
`REDUCE`) require evidence anchors; passive actions (`WAIT`, `HOLD`,
`PAUSE_DCA`) may be anchorless only when insufficient evidence or
review blockage is explicitly recorded.

## Demos

`fund-agent` ships three end-to-end host demos under `examples/`:

- `examples/minimal_host_news_to_decision.py` — news → evidence →
  decision, using only in-memory adapters.
- `examples/minimal_host_portfolio_review.py` — host-supplied
  portfolio → `FundAnalysisSkill` → evidence → decision.
- `examples/minimal_host_trade_plan_to_decisions.py` — host-supplied
  trade plan → `FundAnalysisSkill` → multi-leg decisions.

All three are runnable without any network access, provider SDKs, or
the legacy `ResearchOS` path.

## Realistic example payloads

The `examples/` directory also ships five realistic JSON payloads for
personal portfolio review:

- `examples/portfolio_review_200k.json`
- `examples/oil_gas_loss_rebalance.json`
- `examples/short_term_theme_trade.json`
- `examples/dca_adjustment.json`
- `examples/rebalance_with_cash_reserve.json`

These are the inputs the demos accept. They are version-controlled
test fixtures and are validated by `scripts/check_examples.py`.

## Versioning

`fund-agent` follows semantic versioning. The current version is
`0.4.8`. The canonical sources of truth are:

- `VERSION` — the version string
- `pyproject.toml` — `project.version`
- `skillpack/fund-agent.skillpack.yaml` — `version` and
  `schema_version`
- `package.json` — `version` (for the OpenCode plugin entrypoint)
- `CHANGELOG.md` — release notes

Pin a specific version with a git tag:

```bash
git clone --branch v0.4.8 https://github.com/EXASHXE/fund-agent.git
cd fund-agent
pip install -e .
```

## Updating

```bash
cd /path/to/fund-agent
git pull
pip install -e .   # in case the manifest or pyproject changed
bash scripts/check_plugin_gate.sh
```

## Uninstall

```bash
pip uninstall fund-agent
rm -rf /path/to/fund-agent
```

## Runtime bridge CLI (optional)

`fund-agent` ships a thin **runtime bridge CLI** for hosts that
want a process boundary between their code and the runtime skills
without writing Python import boilerplate. The bridge is
host-agnostic, JSON-in / JSON-out, and does not fetch data, import
provider SDKs, or run an agent loop. It is **independent** of the
OpenCode plugin (the plugin still does not call Python).

```bash
# List the available runtime skills
python scripts/run_skill.py --list-skills --pretty

# Run fund_analysis
python scripts/run_skill.py \
    --skill fund_analysis \
    --input examples/runtime_bridge_fund_analysis_input.json \
    --pretty

# Run decision_support
python scripts/run_skill.py \
    --skill decision_support \
    --input examples/runtime_bridge_decision_support_input.json \
    --pretty
```

For the full contract, MCP boundary behavior, and examples, see
[`docs/install/runtime-bridge-cli.md`](./runtime-bridge-cli.md).

## Separate installs for other harnesses

- **OpenCode:** see [`docs/install/opencode.md`](./opencode.md). The
  OpenCode install is a thin plugin wrapper around this skill pack.
- **Codex:** see [`docs/install/codex.md`](./codex.md). Codex has no
  OMO-style installer; you wire fund-agent into Codex manually.
- **Claude Code, OpenClaw, Hermes:** the manual host install is
  sufficient. No native installer is shipped.
- **Generic Python host:** this document. The Python skill pack is
  the canonical install path for any host that can `pip install`.
- **Process-boundary host:** use the runtime bridge CLI
  ([`docs/install/runtime-bridge-cli.md`](./runtime-bridge-cli.md)).

## Honesty about current capability

- ✅ The Python runtime is fully usable and tested.
- ✅ The five manifest skills are callable.
- ✅ `DecisionSupportSkill` produces audit-friendly decisions.
- ✅ All example payloads are valid against the current schema.
- ❌ `fund-agent` does not fetch any data. The host must do that.
- ❌ `fund-agent` does not place trades. The host must do that.
- ❌ `fund-agent` does not own the agent loop. The host must do that.
