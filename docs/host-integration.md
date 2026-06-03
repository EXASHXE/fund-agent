# Host Integration

`fund-agent` is a host-agnostic skill pack. The external agent host is the
planner and orchestrator. `fund-agent` provides manifest metadata, runtime
skills, schemas, tools, and contracts.

The skill layer is Markdown-first. Hosts should discover callable skills from
`skillpack/fund-agent.skillpack.yaml`, then read `skills/<slug>/SKILL.md` for
agent-facing workflow and policy. Do not infer runtime skill IDs from folder
names.

All data capabilities (fund profiles, NAV history, holdings, transactions,
benchmarks, peer data, manager profiles, fee schedules, market calendar, etc.)
are **host-owned**. `fund-agent` does NOT fetch NAV, holdings, news, sentiment,
or fund profiles directly. The host provides data in `SkillInput.payload`. See
`skillpack/capabilities.yaml` for the full host-owned data capability catalog.

## Responsibilities

- Host agent: planning, skill order, task memory, MCP provider wiring,
  orchestration, retries, and final UX. Host owns all data fetching.
- `fund-agent`: callable skills, pure tools, evidence contracts, graph helpers,
  decision support, deterministic ledger snapshot, and audit-friendly outputs.

Host integrations do not need to call `src.core.research_os`.

## Install Paths

`fund-agent` is host-agnostic. The first native install target is
OpenCode (metadata + docs only); the canonical Python install is the
manual flow; Codex has a manual / light install. See:

- OpenCode: [`docs/install/opencode.md`](./install/opencode.md) and
  [`.opencode/INSTALL.md`](../.opencode/INSTALL.md)
- Manual / Python host: [`docs/install/manual-host.md`](./install/manual-host.md)
- Runtime bridge CLI (host-agnostic, JSON-in / JSON-out subprocess
  over the manifest runtime skills — shipped in v0.4.7-dev):
  [`docs/install/runtime-bridge-cli.md`](./install/runtime-bridge-cli.md)
- Codex: [`docs/install/codex.md`](./install/codex.md)
- Deeper runtime bridge design (subprocess handlers, OpenCode plugin
  `fund_agent_run_skill` tool — still future):
  [`docs/design/runtime-bridge.md`](./design/runtime-bridge.md)
- Other harnesses: [`docs/host-compatibility.md`](./host-compatibility.md)

The OpenCode install does **not** turn `fund-agent` into an autonomous
ResearchOS / planner loop. The plugin exposes three metadata + doc
reader tools (`fund_agent_skills`, `fund_agent_skill_doc`,
`fund_agent_runtime_hint`) and leaves the actual skill invocation to
the manual host integration path.

## Integration Flow

1. Load [`skillpack/fund-agent.skillpack.yaml`](../skillpack/fund-agent.skillpack.yaml).
2. Select a manifest runtime skill ID such as `fund_analysis`.
3. Read the corresponding hyphenated Markdown doc slug such as
   `skills/fund-analysis/SKILL.md`.
4. Resolve the runtime path declared by the manifest.
5. Inject an `MCPHostAdapter` implementation if the skill needs MCP data.
6. Build a `SkillInput`.
7. Call `Skill.run(input)`.
8. Collect `SkillOutput.evidence_items`, `artifacts`, `warnings`, and `errors`.
9. Call `compile_evidence_graph` when the host wants to consolidate evidence.
10. Call `DecisionSupportSkill` when the host wants a formal `Decision` and
   `ExecutionLedger`.
11. Choose any order. `fund-agent` does not impose an agent loop.

Directory naming policy:

- `fund_analysis` is the runtime skill ID.
- `fund-analysis` is the canonical Markdown doc slug.
- `fund-analyst` is legacy/reference-only material.
- Underscore directories under `skills/` are compatibility-only if present.

The callable tool catalog lives at
[`skillpack/tools.yaml`](../skillpack/tools.yaml).

## Pseudocode

### Portfolio Review

For personal portfolio review, the host supplies local or host-fetched fund
data directly to `fund_analysis`. There are two modes:

1. **Direct portfolio mode**: Host provides `portfolio.positions` directly.
2. **Derived portfolio mode**: Host provides `transactions` + `current_nav`
   and `as_of_date`; `fund_analysis` deterministically builds a position
   snapshot from the transaction ledger using weighted-average cost basis.

When both host portfolio and transactions exist, `fund_analysis` runs a
ledger-portfolio reconciliation and emits a `ledger_reconciliation_report`.

`fund-agent` does not fetch NAV, holdings, or profiles.

```python
from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.tools.evidence.validators import compile_evidence_graph

payload = {
    "portfolio": {
        "as_of_date": "2026-06-01",
        "total_value": 200000,
        "cash_available": 20000,
        "positions": [
            {
                "fund_code": "110011",
                "fund_name": "Example Fund",
                "current_value": 30000,
                "total_cost": 32000,
                "target_weight": 0.12,
                "tags": ["healthcare", "active"],
            }
        ],
    },
    "fund_profiles": {"110011": {"fund_code": "110011", "name": "Example Fund"}},
    "nav_history": {"110011": [{"date": "2025-06-01", "nav": 1.0}]},
    "holdings": {"110011": [{"name": "A", "weight": 1.0, "industry": "healthcare"}]},
    "risk_profile": {
        "risk_level": "moderate",
        "max_single_fund_weight": 0.2,
        "max_theme_weight": 0.35,
        "max_trade_pct": 0.1,
        "liquidity_reserve_pct": 0.1,
        "short_term_trade_budget_pct": 0.1,
    },
    "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
}

fund_output = FundAnalysisSkill().run(
    SkillInput(
        task_id="host-task-1",
        step_id="fund-analysis-1",
        skill_name="fund_analysis",
        payload=payload,
    )
)

compile_result = compile_evidence_graph(fund_output.evidence_items)

decision_output = DecisionSupportSkill().run(
    SkillInput(
        task_id="host-task-1",
        step_id="decision-1",
        skill_name="decision_support",
        payload={
            "evidence_graph": compile_result.graph.to_dict(),
            "objective": "personal portfolio review",
            "portfolio_context": payload["portfolio"],
            "risk_profile": payload["risk_profile"],
            "constraints": {"max_buy_amount": 10000, "min_trade_amount": 100},
            "target_trade_amount": 8000,
            "time_horizon": "1 year",
        },
    )
)
```

`fund_output.artifacts` includes `fund_analysis_report`, `portfolio_summary`,
`risk_flags`, `suggested_rebalance_plan`, `data_completeness`,
`analysis_coverage`, and `report_limitations`.

### News To Decision

```python
from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.tools.evidence.validators import compile_evidence_graph

manifest = load_skillpack_manifest("skillpack/fund-agent.skillpack.yaml")

news_spec = manifest.skill("news_research")
news_skill_cls = resolve_runtime("src.skills_runtime.news_research:NewsResearchSkill")
news_skill = news_skill_cls(mcp_adapter=host_mcp)

skill_input = SkillInput(
    task_id="host-task-1",
    step_id="news-1",
    skill_name="news_research",
    payload={"query": "fund:110011"},
    required_mcp_capabilities=news_spec.requires_mcp,
)
news_output = news_skill.run(skill_input)

compile_result = compile_evidence_graph(news_output.evidence_items)

decision_output = DecisionSupportSkill().run(
    SkillInput(
        task_id="host-task-1",
        step_id="decision-1",
        skill_name="decision_support",
        payload={
            "evidence_graph": compile_result.graph.to_dict(),
            "objective": "review fund",
            "risk_budget": {"max_drawdown": 0.1},
            "portfolio_context": {},
            "time_horizon": "1 year",
        },
    )
)
```

## MCP Adapter Injection

`src.tools.adapters.mcp.MCPHostAdapter` is a boundary interface. Host runtimes
can adapt any provider behind it, but provider SDKs must stay outside
`fund-agent` skills.

Skills receive the adapter through their constructor:

```python
news_skill = NewsResearchSkill(mcp_adapter=host_mcp)
```

or through host-specific dependency injection. MCP call results must be
structured dictionaries.

## Process-Boundary Hosts (Runtime Bridge CLI)

Hosts that prefer a process boundary over in-process Python imports
can drive the runtime skills through the **runtime bridge CLI**
shipped in v0.4.7-dev. The bridge reads a JSON envelope from
`--input` (path or `-` for stdin), calls one manifest runtime
skill, and writes a JSON envelope to stdout. It accepts in-memory
MCP canned responses via a `mcp_responses` block and never
imports provider SDKs or makes network calls.

```bash
python scripts/run_skill.py \
    --skill fund_analysis \
    --input examples/runtime_bridge_fund_analysis_input.json \
    --pretty
```

The bridge is **independent of the OpenCode plugin** — the plugin
still does not call Python. See
[`docs/install/runtime-bridge-cli.md`](./install/runtime-bridge-cli.md)
for the full contract, JSON schemas, and MCP boundary behavior. The
deeper runtime-bridge design (subprocess handlers, OpenCode plugin
`fund_agent_run_skill` tool) is still future and lives in
[`docs/design/runtime-bridge.md`](./design/runtime-bridge.md).

## Decision Support

Only `src.skills_runtime.decision_support.DecisionSupportSkill` produces formal
`Decision` and `ExecutionLedger` artifacts. Active actions require real
EvidenceGraph anchors. WAIT/HOLD decisions may be anchorless only when
insufficient evidence is explicitly recorded.

When hosts provide `portfolio_context`, `risk_profile`, `constraints`, or
`target_trade_amount`, `DecisionSupportSkill` derives execution amounts from
those limits instead of using a generic default. If the amount cannot be safely
derived for an active action, it returns a passive action with an audit note.

`src.skills_runtime.thesis_generation.ThesisGenerationSkill` produces a
`thesis_draft` artifact only. It must not produce a formal `Decision`; hosts
should call `DecisionSupportSkill` for that step.

## No Required Workflow

External agents can:

- call only quant/fund analysis,
- collect news and sentiment first,
- compile evidence after every step or once at the end,
- call their own planner,
- skip decision support,
- combine this skill pack with other repositories.

`fund-agent` does not own the agent loop.

ResearchOS is optional reference only, not required for host integrations.
