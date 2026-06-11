# Full Advisory Workflow Architecture — v1.3/v1.4

## Overview

The v1.3/v1.4 full advisory workflow connects fund_analysis, EvidenceGraph
compilation, decision_support, and a final report composer into one coherent,
deterministic, and testable host-agnostic pipeline.

**fund-agent** is a host-agnostic financial research skill pack. It provides
analysis, evidence, decisions, and structured reports — but it **never**
executes broker orders, fetches live data, or runs an autonomous planning loop.

## Workflow Architecture

```
 External Host
   │
   │ owns: user interaction, live data fetching, MCP credentials,
   │       market/news/sentiment/NAV/fee/holding data sources,
   │       broker/order execution (outside fund-agent)
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  1. FundAnalysisSkill                                       │
│     Consumes: host payload (portfolio, transactions, NAV,   │
│               holdings, fees, benchmarks, news, sentiment)  │
│     Produces: evidence_items (HardEvidence),                │
│               analysis artifacts (portfolio_summary,        │
│               position_summary, pnl_summary, risk_flags,   │
│               suggested_rebalance_plan, diagnostics,       │
│               analysis_plan, report_sections, ...)          │
│     Forbidden outputs: Decision, ExecutionLedger            │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  2. EvidenceGraph Bridge (src/tools/workflow/evidence_bridge)│
│     Combines:                                               │
│       - fund_analysis.evidence_items (HardEvidence)         │
│       - host news_evidence → SoftEvidence                   │
│       - host sentiment_evidence → SoftEvidence              │
│       - diagnostic artifacts → HardEvidence                 │
│     Produces: WorkflowEvidenceGraphResult                   │
│       - graph: EvidenceGraph (unified)                      │
│       - included_evidence_count                             │
│       - host_soft_evidence_count                            │
│       - missing_or_invalid_evidence                         │
│       - warnings                                            │
│     Is deterministic. Does not call network/LLM/MCP.        │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  3. DecisionSupportSkill (only if formal action requested)  │
│     Consumes: EvidenceGraph, requested_action, trade_plan,  │
│               portfolio_context, constraints, diagnostics   │
│     Produces: Decision, ExecutionLedger,                    │
│               evidence_anchor_diagnostics,                  │
│               risk_constraint_conflicts                     │
│     Gatekeeping:                                            │
│       - Active actions require valid evidence anchors       │
│       - Fee/redemption blockers block SELL/REDUCE           │
│       - Right-side confirmation required for BUY/INCREASE   │
│       - Cash deployment readiness required for BUY          │
│       - Risk constraints cap amounts                        │
│       - Critique status FAIL/WARN blocks active actions     │
│     Only runtime skill allowed to emit Decision/            │
│     ExecutionLedger.                                        │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Final Report Composer (src/tools/workflow/final_report)  │
│     Consumes: fund_analysis output, decision_support output,│
│               evidence bridge diagnostics, missing data     │
│     Produces: structured final explanation                  │
│       - workflow_summary (scenario_id, report_status,       │
│         decision_status, data_completeness_grade,           │
│         decision_support_ready)                             │
│       - user_facing_sections (summary, evidence_status,     │
│         decision_explanation, limitations)                  │
│       - safety_boundary (no_broker_execution,               │
│         formal_decision_source, analysis_only_sections)     │
│     Is deterministic. Does not use LLM.                     │
│     Does not create decisions.                              │
│     Does not replace fund_analysis report_sections.         │
└─────────────────────────────────────────────────────────────┘
```

## Where Host Data Enters

All live data enters through the host-provided payload to FundAnalysisSkill:

- `portfolio` — positions snapshot
- `transactions` — trade history
- `nav_history` — per-fund NAV time series
- `fund_profiles` — fund metadata, benchmarks, themes
- `holdings` — underlying stock/bond allocations
- `fee_schedules` — management and redemption fees
- `redemption_rules` — holding period requirements
- `benchmark_history` — benchmark index time series
- `news_evidence` — raw news items from host MCP
- `sentiment_evidence` — raw sentiment items from host MCP
- `risk_profile` — user risk preferences
- `constraints` — trade amount caps, forbidden actions
- `trade_plan` / `requested_action` — what the user wants

Missing data is handled gracefully: warnings, blockers, PARTIAL status,
degraded report quality, and blocked formal decisions.

## Where Host Orchestration Happens

The external host/agent owns:

1. Gathering user input and constructing the payload
2. Fetching live data via MCP (web_search, financial_news, social_sentiment)
3. Deciding when to call fund_analysis, evidence bridge, decision_support
4. Interpreting the final report and presenting it to the user
5. Executing broker orders (completely outside fund-agent)

## Why fund-agent Does NOT Execute Broker Orders

fund-agent is an analysis and decision support layer. Broker execution requires:

- Order routing, venue selection, settlement
- Fill confirmation, position reconciliation
- Compliance with broker-specific APIs
- Real-time market connectivity

These belong to the host's execution layer, not to a research skill pack.
The `ExecutionLedger` is an **audit artifact only** — it records what
decisions were proposed, not what was submitted to a broker.

**Forbidden execution fields** that MUST NOT appear in any output:
`broker_order_id`, `order_id`, `order_status`, `filled_quantity`,
`fill_price`, `execution_venue`, `submitted_at`, `broker`,
`exchange_order_id`.

## How suggested_rebalance_plan Differs from Formal Decision

| Aspect | suggested_rebalance_plan | Formal Decision |
|--------|--------------------------|-----------------|
| Producer | fund_analysis | decision_support |
| Evidence requirement | None | EvidenceGraph anchors required |
| Blocked by constraints | No | Yes |
| Can result in broker order | No | No (audit only) |
| User-facing status | "Analysis only" | "Formal decision" |

When `analysis_plan.decision_support_ready` is `false`, the report MUST
clearly state that suggested trades are analysis-only and blocked from
formal decision.

## How Missing Data Degrades the Workflow

| Missing Data | Effect |
|---|---|
| No transactions | Cost basis unknown → PnL degraded, profit protection partial |
| No nav_history | Returns/drawdown unknown → benchmark diagnostics skipped |
| No holdings | KG disabled, overlap diagnostics skipped |
| No fee_schedules | Fee diagnostics partial, redemption blocker may miss |
| No redemption_rules | Short-holding blocker may miss |
| No benchmark_history | Benchmark divergence skipped |
| No news_evidence | News confirmation unavailable → right-side may be unconfirmed |
| No sentiment_evidence | Sentiment unavailable → soft evidence missing |
| No risk_profile | Risk capping cannot apply → formal actions blocked |
| No constraints | Trade capping cannot apply → formal actions blocked |

## How KG Differs from EvidenceGraph

| Aspect | KnowledgeGraph | EvidenceGraph |
|--------|---------------|---------------|
| Scope | Fund→stock→industry→theme relationships | Evidence items with confidence |
| Purpose | Context, cross-fund analysis | Decision support, auditability |
| Producer | fund_analysis (holdings-stage) | evidence bridge (workflow-level) |
| Consumed by | Report sections (exposure, overlap) | decision_support, gatekeeper |
| Formal evidence source | No (must be bridged explicitly) | Yes |

## How MCP / Live Data Remains Host-Owned

fund-agent skills_runtime modules (fund_analysis, decision_support, etc.)
contain **zero** import statements for:

- `tavily`, `finnhub`, `exa`, `firecrawl`, `reddit`, `akshare`
- `openai`, `anthropic`, `langchain`
- `requests`, `httpx`, `urllib` (for external calls)
- Any MCP client library

All network data enters through `SkillInput.payload` — a dict provided
by the host. The `MCPHostAdapter` is an abstract boundary; concrete
implementations live in the host's runtime, not in fund-agent.

## Testing Structure

```
tests/end_to_end/test_advisory_workflows.py   — full workflow tests (131 tests)
tests/evidence/test_workflow_evidence_bridge.py — bridge unit tests (23 tests)
tests/reporting/test_advisory_workflow_report.py — report composer tests (18 tests)
examples/e2e_advisory_workflows/              — 7 realistic JSON fixtures
src/tools/workflow/evidence_bridge.py         — EvidenceGraph bridge
src/tools/workflow/final_report.py            — Final report composer
```

## E2E Scenarios Covered

1. `semiconductor_profit_protection_formal_reduce` — profit protection → formal REDUCE
2. `innovation_drug_drawdown_unconfirmed_right_side` — drawdown → block active BUY
3. `short_holding_fee_sell_blocked` — fee blocker → block active SELL
4. `qdii_ai_overlap_concentration_watch` — overlap → report-only, no formal decision
5. `cash_bond_deployment_budget_guard` — cash deployment → budget constraints
6. `all_data_sufficient_formal_trade_plan` — complete data → multi-leg trade plan
7. `missing_data_report_only_no_fabrication` — missing data → report-only, no fabrication

## Version

Workflow architecture v1.3/v1.4 — full advisory flow optimization.
