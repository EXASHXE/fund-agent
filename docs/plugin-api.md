# Plugin API — Host Integration Reference

This document is the authoritative API reference for external agent hosts
(OpenCode, Claude Code, Codex, OpenClaw, Hermes) that integrate the
`fund-agent` skill pack.

## 1. Plugin Identity

| Field | Value |
|---|---|
| Package name | `fund-agent` |
| Manifest path | `skillpack/fund-agent.skillpack.yaml` |
| Schema version | `skillpack.v1` |
| Package role | `agent_plugin` |
| Orchestration owner | `external_agent` |
| MCP provider owner | `external_host` |

## 1.1 Markdown-First Skill Layer

External hosts use `skillpack/fund-agent.skillpack.yaml` for skill discovery
and runtime paths. The `skills/<slug>/SKILL.md` files are the primary
agent-facing instructions for workflow, policy, constraints, and report style.
Longer materials live in `skills/<slug>/references/*.md`.

Do not infer runtime skill IDs from folder names. For example, `fund_analysis`
is the runtime skill ID and `fund-analysis` is the canonical Markdown doc slug.
`fund-analyst` is legacy/reference-only material, not a runtime entrypoint.

## 2. Required Host Responsibilities

The external host MUST provide:

- **Orchestration** — task decomposition, skill ordering, retry policy
- **MCP provider injection** — implement `MCPHostAdapter` with real providers
- **User interaction** — final UX, display, and user prompts
- **Retry policy** — handle transient failures and `SkillOutput.errors`
- **Provider credentials** — API keys, rate limits, network access
- **Data capabilities** — all fund/profile/NAV/holdings/transaction/benchmark/peer/manager/fee/calendar/macro data is host-owned and host-provided via `SkillInput.payload`. See `skillpack/capabilities.yaml` for the complete host-owned data capability catalog.

`fund-agent` does NOT own the agent loop, does NOT manage credentials, and
does NOT make network requests outside the MCP adapter boundary.

## 3. Runtime Skills

| Runtime skill ID | Markdown doc slug |
|---|---|
| `fund_analysis` | `fund-analysis` |
| `news_research` | `news-research` |
| `sentiment_analysis` | `sentiment-analysis` |
| `thesis_generation` | `thesis-generation` |
| `decision_support` | `decision-support` |

### 3.1 fund_analysis

```
Runtime: src.skills_runtime.fund_analysis:FundAnalysisSkill
Requires MCP: []
Produces: HardEvidence
```

**Personal portfolio payload** — `fund_analysis` accepts an expanded payload
with transactions, dca_plans, cost_basis, market_scenario, and risk
constraints. See `examples/portfolio_review_200k.json` for the full shape.

**Two portfolio input modes:**

1. **Direct mode**: Provide `portfolio.positions` as source of truth.
2. **Derived mode**: Provide `transactions` + `current_nav` + `as_of_date`;
   `fund_analysis` deterministically derives position snapshot from the
   transaction ledger using weighted-average cost basis. Emits
   `derived_portfolio_snapshot` and `ledger_cashflow_summary` artifacts.

When both host portfolio and transactions exist, the skill runs a ledger
reconciliation and emits `ledger_reconciliation_report`.

**Research query planning**: When `payload.research_planning` is `true`,
the skill generates a `research_query_plan` artifact with news/sentiment
queries. This is a plan only — the host decides whether to call
`news_research` or `sentiment_analysis`. No network calls are made.

**Optional data pass-through**: Benchmarks, peer group, factor exposures,
manager profiles, fee schedules, redemption rules, and other host-provided
data are passed through to the report and artifacts without fabricating
rankings or comparisons. Missing data is reflected in `data_completeness`
and `analysis_coverage` artifacts, with a grade (A-D) and coverage map.
The deterministic report composer converts these artifacts into ordered
`report_sections` and a `report_quality_gate` for host display.

Analyzes host-provided personal portfolio data: positions, fund profiles,
NAV history, holdings, risk profile, and rebalance constraints. Returns
portfolio summary artifacts, risk flags, optional suggested rebalance plan,
`data_completeness`, `analysis_coverage`, `report_limitations`, and
structured `report_sections` with a `report_quality_gate`. Returns
`HardEvidence` items with `confidence_weight=1.0`. No MCP capabilities are
required and no data is fetched by the skill. Formal `Decision` and
`ExecutionLedger` outputs remain exclusive to `decision_support`.

**SkillInput shape:**
```json
{
  "task_id": "host-task-001",
  "step_id": "fa-1",
  "skill_name": "fund_analysis",
  "payload": {
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
          "tags": ["healthcare", "active"]
        }
      ]
    },
    "fund_profiles": {
      "110011": {
        "fund_code": "110011",
        "name": "Example Fund",
        "fund_type": "active"
      }
    },
    "nav_history": {
      "110011": [
        {"date": "2025-06-01", "nav": 1.0},
        {"date": "2026-06-01", "nav": 1.2}
      ]
    },
    "holdings": {
      "110011": [
        {"name": "A", "weight": 0.08, "industry": "pharma", "region": "CN"}
      ]
    },
    "risk_profile": {
      "risk_level": "moderate",
      "max_single_fund_weight": 0.2,
      "max_theme_weight": 0.35,
      "max_trade_pct": 0.1,
      "liquidity_reserve_pct": 0.1,
      "short_term_trade_budget_pct": 0.1
    },
    "constraints": {
      "min_trade_amount": 100,
      "forbidden_actions": []
    }
  }
}
```

**SkillOutput shape:**
```json
{
  "step_id": "fa-1",
  "status": "OK",
  "evidence_items": [...],
  "artifacts": {
    "fund_analysis_report": {},
    "portfolio_summary": {},
    "risk_flags": [],
    "suggested_rebalance_plan": {},
    "data_completeness": {},
    "analysis_coverage": {},
    "report_limitations": [],
    "report_sections": [],
    "report_outline": [],
    "report_quality_gate": {
      "grade": "A",
      "can_publish_professional_report": true,
      "reason": "Data completeness grade A supports a professional report."
    }
  },
  "warnings": [],
  "errors": []
}
```

If only `related_entities` is provided, `fund_analysis` keeps a compatibility
fallback and returns baseline HardEvidence with an explicit warning.

### 3.2 news_research

```
Runtime: src.skills_runtime.news_research:NewsResearchSkill
Requires MCP: [web_search, financial_news]
Produces: SoftEvidence
```

Searches for news related to fund holdings. Requires MCP web search and
financial news capabilities injected by the host via `MCPHostAdapter`.
Returns `SoftEvidence` items suitable for compilation into an evidence graph.

**SkillInput shape:**
```json
{
  "task_id": "host-task-001",
  "step_id": "news-1",
  "skill_name": "news_research",
  "required_mcp_capabilities": ["web_search", "financial_news"],
  "payload": {
    "related_entities": ["fund:110011"]
  }
}
```

### 3.3 sentiment_analysis

```
Runtime: src.skills_runtime.sentiment_analysis:SentimentAnalysisSkill
Requires MCP: [social_sentiment]
Produces: SoftEvidence
```

Analyzes sentiment signals for fund-related entities. Requires MCP social
sentiment capability injected by the host.

### 3.4 thesis_generation

```
Runtime: src.skills_runtime.thesis_generation:ThesisGenerationSkill
Requires MCP: []
Produces: ThesisDraft (artifact, NOT a formal Decision)
Forbidden: formal_decision_generation
```

Generates an investment thesis draft from collected evidence. This skill
MUST NOT produce a formal `Decision` or `ExecutionLedger`. Only
`decision_support` may produce those.

### 3.5 decision_support

```
Runtime: src.skills_runtime.decision_support:DecisionSupportSkill
Requires MCP: []
Consumes: EvidenceGraph
Produces: Decision, ExecutionLedger
```

**The ONLY skill that produces formal Decision and ExecutionLedger.**
Consumes a compiled `EvidenceGraph`, evaluates evidence quality and conflict,
and produces a structured `Decision` with anchored rationale and an
`ExecutionLedger` listing all decisions.
When portfolio context and risk constraints are provided, execution amounts are
bounded by cash, max trade percentage, max buy/sell amounts, minimum trade size,
and requested trade amount. If a safe active trade amount cannot be derived, the
skill downgrades to `WAIT` or `HOLD` with an audit-trail explanation.

**SkillInput shape:**
```json
{
  "task_id": "host-task-001",
  "step_id": "decision-1",
  "skill_name": "decision_support",
  "payload": {
    "evidence_graph": {...},
    "objective": "review fund",
    "portfolio_context": {
      "total_value": 200000,
      "cash_available": 20000
    },
    "risk_profile": {"risk_level": "moderate", "max_trade_pct": 0.1},
    "constraints": {"max_buy_amount": 10000, "min_trade_amount": 100},
    "target_trade_amount": 8000,
    "time_horizon": "1 year"
  }
}
```

**SkillOutput shape:**
```json
{
  "task_id": "host-task-001",
  "step_id": "decision-1",
  "status": "OK",
  "artifacts": {
    "decision": {...},
    "execution_ledger": {...}
  },
  "errors": []
}
```

## 4. Tool Catalog Summary

| Tool | Path | Category | Produces |
|---|---|---|---|
| `compile_evidence_graph` | `src.tools.evidence.validators:compile_evidence_graph` | evidence | `EvidenceGraph` |
| `build_hard_evidence_from_metric` | `src.tools.evidence.builders:build_hard_evidence_from_metric` | evidence | `HardEvidence` |
| `build_soft_evidence_from_mcp_result` | `src.tools.evidence.builders:build_soft_evidence_from_mcp_result` | evidence | `SoftEvidence` |
| `review_evidence_graph` | `src.tools.evidence.review:review_evidence_graph` | evidence | `ReviewReport` |
| Quant metrics | `src.tools.quant.*` | quant | Various metrics |
| Fund metrics | `src.tools.fund.metrics:*` | fund | NAV returns and risk-return metrics |
| Portfolio analysis | `src.tools.portfolio.analysis:*` | portfolio | Weights, exposures, risk flags, rebalance simulation |
| Ledger tools | `src.tools.ledger.*` | ledger | Ledger entries |
| `MCPHostAdapter` | `src.tools.adapters.mcp:MCPHostAdapter` | adapter | MCP boundary |

Full catalog: `skillpack/tools.yaml`.

## 5. Minimal Host Flow

```python
from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.schemas.skill import SkillInput
from src.tools.evidence.validators import compile_evidence_graph
from src.skills_runtime.decision_support import DecisionSupportSkill

# 1. Load manifest
manifest = load_skillpack_manifest("skillpack/fund-agent.skillpack.yaml")

# 2. Resolve runtime skill
news_spec = manifest.skill("news_research")
news_cls = resolve_runtime(news_spec.runtime)

# 3. Inject MCP adapter (host provides this)
news_skill = news_cls(mcp_adapter=host_mcp)

# 4. Build SkillInput
task_input = SkillInput(
    task_id="host-task-1",
    step_id="news-1",
    skill_name="news_research",
    payload={"related_entities": ["fund:110011"]},
    required_mcp_capabilities=news_spec.requires_mcp,
)

# 5. Call skill
news_output = news_skill.run(task_input)

# 6. Collect evidence
evidence_items = news_output.evidence_items

# 7. Compile evidence graph
compile_result = compile_evidence_graph(evidence_items)

# 8. Call decision support
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

decision = decision_output.artifacts["decision"]
ledger = decision_output.artifacts["execution_ledger"]
```

The host is free to reorder steps, skip skills, or combine with other packs.

## 6. Error Handling

All skills return errors via `SkillOutput.errors`. Each error uses the
`SkillError` schema:

| Field | Type | Description |
|---|---|---|
| `code` | `str` | Standard error code |
| `message` | `str` | Human-readable description |
| `details` | `dict` | Context-specific details (default `{}`) |
| `recoverable` | `bool` | Whether the host can retry (default `True`) |

### SkillError Codes / Standard Error Codes

| Code | Meaning | Recoverable |
|---|---|---|
| `MISSING_MCP_CAPABILITY` | Required MCP capability not available | Usually no |
| `MCP_CALL_FAILED` | MCP provider call failed | Yes |
| `INVALID_INPUT` | SkillInput payload is malformed | No |
| `EVIDENCE_BUILD_FAILED` | Evidence construction failed | Yes |
| `EMPTY_RESULT` | No evidence or artifacts produced | Yes |
| `INTERNAL_ERROR` | Unexpected internal error | No |
| `CONTRACT_VIOLATION` | Skill contract violated (e.g. thesis producing Decision) | No |

```python
output = skill.run(my_input)
for err in output.errors:
    if err["recoverable"]:
        # host may retry
        pass
    else:
        # host should log and abort the flow
        pass
```

## 7. Decision Safety

- **Only `decision_support`** may produce formal `Decision` and `ExecutionLedger`.
- **Active decisions** (`BUY`, `SELL`, `INCREASE`, `REDUCE`) MUST anchor to
  real `EvidenceGraph` evidence IDs via `rationale_anchor`.
- **Passive decisions** (`WAIT`, `HOLD`, `PAUSE_DCA`) may have empty anchors
  only when insufficient evidence or review blockage is explicitly recorded.
- **`thesis_generation`** produces only `ThesisDraft` artifacts; it is
  forbidden from producing formal `Decision` objects.

## 8. What NOT To Do

- Do NOT call `src.core.research_os` as a required host integration path.
- Do NOT import `legacy` modules from plugin code.
- Do NOT hardcode Tavily, Finnhub, Exa, Firecrawl, Reddit, AkShare, OpenAI,
  Anthropic, LangChain, or other provider SDKs in skill runtimes.
- Do NOT let `thesis_generation` produce a `Decision`.
- Do NOT make network calls in `src/tools` outside the MCP adapter boundary.
- Do NOT treat the optional reference workflows as the official entrypoint.
