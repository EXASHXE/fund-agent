# v1 Analysis Pipeline

## Workflow

```
External agent / host
  → collect holdings, transactions, NAV, fee schedule,
    fund metadata, news, sentiment, benchmark
  → call fund_analysis
  → read analysis_plan and evidence_gap_diagnostics
  → call news_research / sentiment_analysis / thesis_generation
    as recommended by analysis_plan
  → call decision_support only when decision_support_ready is true
  → render final report
```

## Key principles

- **analysis_plan is an artifact, not an autonomous planner.**
  The external host/agent owns all orchestration decisions.
  fund-agent never autonomously calls another skill or fetches data.

- **OpenCode plugin adapter is metadata + doc-reader only.**
  It does not launch Python, call the runtime bridge, fetch live data,
  or manage MCP servers.

- **Deterministic runtime does not fetch live data.**
  All computation is local-only from host-supplied payloads.
  No network calls, no provider SDKs, no LLM calls.

- **Host owns orchestration and credentials.**
  The host decides which skills to call, in what order, with what data.
  The host provides all MCP credentials and manages data providers.

## Pipeline stages

```
input_stage
  → ledger_stage
  → metrics_stage
  → optional_data_stage
  → diagnostics_stage
  → planning_stage       ← new in v1
  → report_stage
  → status_stage
```

`planning_stage` consumes the outputs of diagnostics and optional data
to produce `analysis_plan` and `evidence_gap_diagnostics` artifacts.

## analysis_plan artifact

| Field | Type | Description |
|---|---|---|
| `user_goal` | string | User's stated goal (if provided) |
| `available_inputs` | list | Data dimensions present in the input |
| `missing_inputs` | list | Data dimensions absent or insufficient |
| `recommended_skill_sequence` | list | Skills to call next, in order |
| `recommended_mcp_capabilities` | list | Provider-agnostic MCP capabilities to inject |
| `evidence_requirements` | list | Evidence needed before actionable advice |
| `decision_support_ready` | bool | Whether evidence is sufficient for decision_support |
| `blockers` | list | Items that prevent formal decision_support |
| `warnings` | list | Non-blocking concerns |
| `next_data_to_fetch` | list | Concrete data items the host should obtain |

## evidence_gap_diagnostics artifact

| Field | Type | Description |
|---|---|---|
| `missing_holdings` | bool | No portfolio positions provided |
| `missing_transaction_history` | bool | No transaction ledger provided |
| `missing_fund_metadata` | bool | No fund profiles provided |
| `missing_fee_schedule` | bool | No fee schedules or redemption rules provided |
| `missing_nav_history` | bool | No NAV history provided |
| `missing_benchmark_data` | bool | No benchmark data provided |
| `missing_recent_news` | bool | Always true (news must come from host/MCP) |
| `missing_sentiment` | bool | Always true (sentiment must come from host/MCP) |
| `missing_holdings_detail` | bool | No fund holdings detail provided |
| `missing_user_constraints` | bool | No user constraints provided |
| `missing_risk_preference` | bool | No risk profile provided |
| `details` | list | Severity-coded gap details with recommended next data |

## decision_support_ready rules

`decision_support_ready` is `true` only when ALL of:

- Holdings are available
- Deterministic metrics are available
- No blocking fee/redemption risk is present
- Recent evidence is available enough for an active recommendation
- No other blockers exist

In Phase 1, this is intentionally conservative. Many realistic scenarios
will return `false` because `missing_recent_news` is always true until
the host injects news evidence.

## Phase 3: Evidence-aware diagnostics

Phase 3 adds four deterministic diagnostic artifacts that consume
host-provided evidence without fetching data:

### benchmark_divergence_diagnostics

Compares fund NAV return against benchmark return when host provides
both `nav_history` and `benchmark_history`. Produces `divergence_level`
(`none | mild | moderate | severe | unknown`) and `divergence_direction`
(`outperforming | underperforming | in_line | unknown`). When benchmark
data is missing, `evidence_state` is `missing` and `analysis_plan` adds
benchmark data to `next_data_to_fetch`.

### right_side_confirmation_diagnostics

Assesses whether a rebound/confirmation exists for drawdown positions.
Uses NAV, benchmark, news, and sentiment evidence. `right_side_confirmed`
is true only when nav rebound is confirmed, benchmark is not negative,
and news/sentiment are not negative. When unconfirmed for action-oriented
user goals, `right_side_unconfirmed` appears in `analysis_plan.blockers`.

### event_hype_failure_diagnostics

Detects scenarios where an expected positive catalyst/event failed to
produce the expected price reaction. Uses host-provided `events` or
`catalyst_events` metadata plus NAV and news data. `suggested_analysis_action`
is always analysis-only (`watch | reduce_hype_weight | data_needed`).
High-risk hype failures add `event_hype_failed` to `analysis_plan.warnings`
or `analysis_plan.blockers`.

### cash_deployment_diagnostics

Evaluates cash-like allocation, buffer status, and deployment readiness.
Does not recommend specific buys. When `deployment_readiness` is
`not_ready`, `cash_deployment_not_ready` appears in `analysis_plan.warnings`
or `analysis_plan.blockers`.

### Pipeline stages (updated)

```
input_stage
  → ledger_stage
  → metrics_stage
  → optional_data_stage
  → diagnostics_stage
  → position_contribution
  → profit_protection_diagnostics
  → benchmark_divergence_diagnostics
  → right_side_confirmation_diagnostics
  → event_hype_failure_diagnostics
  → cash_deployment_diagnostics
  → planning_stage       ← consumes Phase 3 diagnostics
  → report_stage
  → status_stage
```

All Phase 3 diagnostics are deterministic, local-only, and do not fetch
live data. Missing evidence is surfaced as gaps, not hallucinated.
