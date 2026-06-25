---
name: fund-analysis
version: "0.10.6"
id: fund_analysis
runtime: src.skills_runtime.fund_analysis:FundAnalysisSkill
runtime_id: fund_analysis
runtime_class: src.skills_runtime.fund_analysis:FundAnalysisSkill
input_schema: src.schemas.skill:SkillInput
output_schema: src.schemas.skill:SkillOutput
category: primary
role: primary
requires_mcp: []
required_mcp_capabilities: []
produces: [HardEvidence, report_sections, report_outline, report_quality_gate, data_completeness]
forbidden: [formal_decision_generation, execution_ledger_production]
description: Primary portfolio and fund report entrypoint for personal fund analysis
entrypoint: skills/fund-analysis/SKILL.md
---

# Fund Analysis

## User intent trigger

When the user requests any of the following, the agent MUST enter the
**autonomous personal analysis workflow** — no further disambiguation needed:

- "分析我的基金组合" / "分析下我的基金"
- "做一次个人基金组合分析" / "个人基金体检"
- "新的流水数据在 private_data"
- "用 fund-analysis skill 分析" / "跑 fund-agent 分析我的基金"
- "请使用本仓库的 fund-analysis skill 做一次个人基金组合分析"

The user does NOT need to explicitly write:
- `personal-run`
- `agent_context`
- `--no-skip-akshare`
- forbidden paths or safety constraints

All of these are specified by this SKILL.md. The agent reads this file and
follows the rules automatically.

## Canonical personal analysis entrypoint

For personal portfolio analysis, the **only canonical entrypoint** is:

```bash
bin/fund-agent-personal-run \
  --private-data-dir private_data \
  --output-dir local_reports \
  --transaction-source auto \
  --no-skip-akshare \
  --skip-news
```

- `--no-skip-akshare` enables live NAV for real valuations (default for real analysis).
- `--skip-news` remains on — news requires explicit user request.
- If the user specifies a different data directory, replace `--private-data-dir`.
- If the user does not specify a directory, try `private_data` first; if it does not
  exist, ask the user.

### Canonical artifact path

After a successful run, the canonical output is:

```
local_reports/<run_id>/
```

This directory MUST contain:
- `agent_context.json` — machine-readable status, scope, and constraints
- `agent_context.md` — human-readable summary
- `e2e_summary.json` — full pipeline summary
- `personal_health_report.json` — data quality diagnostic and fix-it checklist
- `report.md` — composed report

If these files do not exist, the agent MUST:
1. Stop.
2. Report pipeline failure.
3. NOT synthesize a portfolio report on its own.

### Forbidden non-canonical paths

For personal portfolio analysis, agents MUST NOT:

- Call `FundAnalysisSkill().run()` directly
- Construct `SkillInput` manually
- Read `confirmed_portfolio.private.json` as final report input
- Create `local_reports/run_skill_analysis.py`
- Use `local_reports/skill_output` as personal analysis result
- Convert missing `current_value` / `null` / `None` to `0.0`
- Calculate P&L, HHI, max holding, contribution, cash reserve, or risk flags
  from `cashflow_only` or `valuation_blocked` positions
- Continue analysis if `agent_context.json` is missing

`FundAnalysisSkill` is an internal runtime component. It exists as a
programmable skill for host integration, but for personal portfolio analysis
the agent MUST use `bin/fund-agent-personal-run` and read the canonical
artifact package. The skill runtime is NOT the user-facing entrypoint.

`local_reports/skill_output` is legacy / non-canonical. It must NOT be used
for personal analysis.

## Default entrypoint

`fund-analysis` is the **primary / default skill** in the
`fund-agent` Superpowers-compatible skill collection. For ordinary
portfolio and fund report requests — for example
`分析下我的基金给出报告` — load `fund-analysis` first. It alone is
sufficient for a report-only flow.

`fund-analysis` itself maps to the Python runtime ID `fund_analysis`
declared in `skillpack/fund-agent.skillpack.yaml`. The agent-facing
skill name is the hyphenated slug `fund-analysis`; the underscore
`fund_analysis` is the runtime ID only.

## When to load supporting skills

Load a supporting skill only when the subtask description matches,
and only after `fund-analysis` (or equivalent evidence) is in scope:

| Need | Supporting skill |
|---|---|
| Formal trade / action decision (BUY, SELL, INCREASE, REDUCE, WAIT, HOLD) | `decision-support` |
| News context (recent or historical news for a fund, holding, theme, manager, or macro topic) | `news-research` |
| Sentiment context (social / market mood signals) | `sentiment-analysis` |
| Thesis synthesis (a draft investment thesis before any formal decision) | `thesis-generation` |

Rules of thumb:

- For an ordinary portfolio report, `fund-analysis` alone is
  sufficient. Do not load `decision-support` for a report-only
  request.
- For actionable trade decisions, load `decision-support` **only
  after** an `EvidenceGraph` and optional trade plan exist.
  `decision-support` is the only skill that may produce a formal
  `Decision` / `ExecutionLedger`.
- For news / sentiment / thesis context, load the relevant
  supporting skill only if the host has the required MCP capability
  (news / sentiment) or the required evidence context (thesis).
  None of these supporting skills is required for a normal
  `fund-analysis` flow.
- The legacy `fund-analyst` persona material is archived under
  `docs/archive/fund-analyst/`. Do not load it as a runtime skill.

## Purpose

Use `fund_analysis` to turn host-provided fund and portfolio data into
deterministic portfolio artifacts, risk flags, warnings, `HardEvidence`,
and an `analysis_plan` that tells the external host/agent what data is
available, what is missing, which skills to call next, and whether
`decision_support` is ready. This skill is the analytical layer for
personal fund review. It is not a trade decision engine and never emits
formal `Decision` or `ExecutionLedger` objects.

## When to use this skill

- The user asks for a fund or portfolio report, for example
  `分析下我的基金给出报告`.
- The host has portfolio positions, fund profiles, NAV history, holdings, or
  transaction data to analyze locally.
- The host needs `portfolio_summary`, `exposure_summary`, `risk_flags`,
  `fund_analysis_report`, `suggested_rebalance_plan`, or HardEvidence.
- The host wants deterministic portfolio structure, concentration, DCA,
  short-term trade budget, cost basis, PnL, or market scenario analysis.

## When not to use this skill

- Do not use it to fetch NAV, holdings, market news, or social sentiment.
- Do not use it to produce formal BUY, SELL, INCREASE, REDUCE, WAIT, or HOLD
  decisions. Escalate to `decision_support` for formal decisions.
- Do not use it as an autonomous planner or agent loop.
- Do not use it when the only need is news or sentiment evidence.

## Host responsibilities

The host owns planning, orchestration, user prompts, data fetching, MCP
providers, credentials, market scenario selection, final report UX, and any
decision to call `decision_support`. The host must provide all market, fund,
portfolio, transaction, and scenario data in `SkillInput.payload`.

## Inputs

Runtime skill ID: `fund_analysis`.
Runtime: `src.skills_runtime.fund_analysis:FundAnalysisSkill`.
MCP capabilities required: none.

### Required data

- `portfolio.as_of_date`
- `portfolio.total_value`
- `portfolio.cash_available`
- `portfolio.positions[]` with `fund_code`, `current_value`, and preferably
  `total_cost`, `shares`, `target_weight`, and tags
- `risk_profile` with concentration, liquidity, and trade budget limits
- `constraints` such as minimum trade amount and forbidden actions

### Derived portfolio mode

When `portfolio.positions` is not available, `fund_analysis` accepts:
- `transactions` — transaction ledger with BUY/SELL/DIVIDEND/FEE events
- `current_nav` — `{fund_code: current_nav}` map
- `as_of_date` — the snapshot date

The skill deterministically derives a position snapshot from the ledger
using weighted-average cost basis. Emits `derived_portfolio_snapshot` and
`ledger_cashflow_summary` artifacts with a warning that the portfolio was
derived. Accuracy depends on transaction ledger completeness and current NAV.

### Reconciliation

When both host portfolio and transactions exist, `fund_analysis` runs a
ledger-portfolio reconciliation and emits `ledger_reconciliation_report`.
Mismatches are listed as warnings; analysis continues on the host portfolio
as source of truth.

### Optional data

- `fund_profiles` for fund type, benchmark, manager, and tags
- `nav_history` for deterministic risk-return metrics
- `holdings` for theme, industry, region, and security exposure
- `transactions` for cost basis, cashflow, trading discipline analysis,
  and optional ledger-derived portfolio snapshot
- `dca_plans` for recurring investment review
- `market_scenario` supplied by the host
- `benchmarks`, `benchmark_history`, `peer_group`, `factor_exposures`,
  `manager_profiles`, `fee_schedules`, `redemption_rules` — pass-through
  optional data (host-owned, not fetched by fund-agent)
- `research_planning` — when `true`, produces `research_query_plan` artifact
- `report_options.language` — optional deterministic report language. Supported
  values are `en` (default) and `zh-CN`; unknown values fall back to English.
  `zh-CN` changes report section titles and common deterministic bullet
  templates only. It does not call an LLM or fetch live data.

See `references/input-contract.md` for the expanded payload contract.

## Missing-data degradation policy

Proceed with `PARTIAL` analysis when enough portfolio data exists to calculate
structure and risk. The skill computes a formal `data_completeness` score
(0.0-1.0) and grade (A-D) via `calculate_data_completeness()`. Grades C or D
trigger `PARTIAL` status automatically. Emit explicit `warnings` for missing
fund profiles, NAV history, holdings, transactions, DCA plans, or scenario
data. Do not fabricate missing data. A direct `portfolio.positions` snapshot or
a derived snapshot from `transactions` + `current_nav` is required for
structured portfolio analysis. Missing `risk_profile` or `constraints` lowers
the grade and adds limitations but does not necessarily fail. Missing
`nav_history` or `holdings` marks performance or holding sections
`PARTIAL`/`MISSING`. If `portfolio.positions` is absent or empty and no derived
snapshot can be built, return an `INVALID_INPUT` error. If only
`related_entities` is supplied, use the baseline HardEvidence compatibility
path and warn that structured portfolio analysis was not possible.

## Standard workflow

1. Validate the host payload.
2. Normalize the portfolio view around `as_of_date`.
3. Analyze portfolio structure before individual fund performance.
4. Calculate cash ratio, position weights, concentration, and exposure.
5. Calculate fund metrics only from host-provided NAV history.
6. Review transactions, cost basis, DCA plans, and short-term budget when
   supplied.
7. Apply host-provided market scenario if supplied.
8. Emit artifacts, warnings, and HardEvidence.
9. Leave formal decisions to `decision_support`.

## Portfolio analysis order

Always start with portfolio-level structure:

1. Total value, cash reserve, and cash ratio.
2. Position weights and single-fund concentration.
3. Fund type, theme, region, and industry exposure.
4. Cost and unrealized PnL by position.
5. Individual fund NAV metrics.
6. DCA health and short-term trading budget.
7. Optional suggested rebalance plan.

Check cash reserve before recommending buys. Check single-fund, theme, and
industry concentration before suggesting any trade.

## Risk analysis principles

- Loss does not automatically mean sell.
- Profit does not automatically mean chase or reduce.
- Concentration can matter more than recent return.
- Weak NAV performance should be weighed against thesis, exposure, drawdown,
  risk budget, and cashflow.
- WAIT/HOLD language must be explained, not used as filler.

See `references/risk-policy.md`.

## Short-term trade budget policy

Short-term theme trades must be capped by
`risk_profile.short_term_trade_budget_pct`. If a suggested trade would exceed
the budget, cap it, warn, or avoid suggesting the active trade. The skill may
emit `short_term_trade_budget` and capped trade plan details, but the formal
trade decision still belongs to `decision_support`.

See `references/short-term-trade-policy.md`.

## DCA review policy

DCA changes should consider long-term thesis, available cashflow,
concentration, drawdown, and whether the DCA plan is reinforcing an overweight
position. Do not pause DCA merely because the latest PnL is negative.

See `references/dca-policy.md`.

## Market scenario policy

Market crash, drawdown, stress, or regime scenarios must be host-provided.
`fund-agent` must not fetch, infer, or invent a scenario. If no scenario is
provided, omit scenario claims or mark the scenario gap in warnings.

See `references/market-scenario-policy.md`.

## Analysis plan and evidence gaps

`fund_analysis` now outputs two additional artifacts:

### analysis_plan

A deterministic artifact that tells the external host/agent:

- **available_inputs**: what data the skill already received.
- **missing_inputs**: what data is absent or insufficient.
- **recommended_skill_sequence**: which skills to call next, in order.
- **recommended_mcp_capabilities**: provider-agnostic MCP capabilities
  the host should inject (e.g. `market_news_search`, `benchmark_price_history`).
- **evidence_requirements**: what evidence is needed before actionable advice.
- **decision_support_ready**: whether the evidence is sufficient to call
  `decision_support`. Default is `false`; only `true` when holdings,
  deterministic metrics, fee data, and recent evidence are all available
  and no blockers exist.
- **blockers**: items that prevent formal `decision_support` (e.g.
  `missing_holdings`, `missing_recent_news`, `redemption_fee_blocker`).
- **warnings**: non-blocking concerns (e.g. `sentiment_missing`,
  `benchmark_data_missing`, `theme_overweight_warning`).
- **next_data_to_fetch**: concrete data items the host should obtain next.

**Important**: `analysis_plan` is a deterministic artifact for the
external host/agent to consume. It is NOT an autonomous planner. The
host/agent owns all orchestration decisions.

### evidence_gap_diagnostics

Structured booleans for missing inputs:

- `missing_holdings`, `missing_transaction_history`,
  `missing_fund_metadata`, `missing_fee_schedule`,
  `missing_nav_history`, `missing_benchmark_data`,
  `missing_recent_news`, `missing_sentiment`,
  `missing_holdings_detail`, `missing_user_constraints`,
  `missing_risk_preference`
- `details`: list of `{code, severity, recommended_next_data}` items.

### position_contribution

Per-position PnL contribution analysis:

- `positions`: list of `{position_id, fund_code, fund_name, current_value,
  invested_amount, absolute_pnl, pnl_pct, portfolio_weight,
  pnl_contribution_pct, risk_contribution_hint}`
- `summary`: `{largest_value_position, largest_profit_contributor,
  largest_loss_contributor, high_weight_low_contribution_positions,
  small_weight_high_volatility_hint_positions}`
- When `invested_amount` is unavailable, PnL fields are `null` and
  `risk_contribution_hint` is `low_data`.

### profit_protection_diagnostics

Analysis-only artifact for high-profit positions. **Not a formal decision.**

- `items`: list of `{fund_code, fund_name, current_value, invested_amount,
  absolute_pnl, pnl_pct, profit_level, principal_recovered,
  free_carry_estimate, trim_pressure, hold_pressure, watch_condition,
  suggested_analysis_action}`
- `profit_level`: `none | low | moderate | high | very_high | unknown`
- `suggested_analysis_action`: always analysis-only — `watch | hold_bias |
  trim_review | data_needed`. Never BUY/SELL/TRIM as a formal decision.
- `principal_recovered` and `free_carry_estimate` require transaction
  history; otherwise `unknown`.

### Fee blocker vs warning

`redemption_fee_risk` now includes:

- `fee_items`: list of `{fund_code, fund_name, level, reason, fee_pct,
  holding_days, threshold_days, current_value, absolute_pnl, pnl_pct}`
- `level`: `blocker` (short holding + high fee + loss/unknown PnL) or
  `warning` (short holding but profitable or small fee)
- `has_blocker`: boolean — when true, `redemption_fee_blocker` appears in
  `analysis_plan.blockers` and `decision_support_ready` is false
- `has_warning`: boolean — when true, `redemption_fee_warning` appears in
  `analysis_plan.warnings`

Legacy `affected_funds` and `summary` fields remain for backward
compatibility.

### benchmark_divergence_diagnostics

Deterministic benchmark divergence analysis. Compares fund NAV return
against benchmark return when host provides both series. Analysis-only;
not a formal decision.

- `items`: list of `{fund_code, fund_name, benchmark_id, fund_return_pct,
  benchmark_return_pct, excess_return_pct, divergence_level,
  divergence_direction, evidence_state, missing_reason, lookback_days}`
- `divergence_level`: `none | mild | moderate | severe | unknown`
- `divergence_direction`: `outperforming | underperforming | in_line | unknown`
- `evidence_state`: `sufficient | missing | weak`
- When benchmark history is missing, `evidence_state` is `missing` and
  `analysis_plan.next_data_to_fetch` includes benchmark data

### right_side_confirmation_diagnostics

Deterministic right-side confirmation assessment. For drawdown positions,
evaluates whether a rebound/confirmation exists based on NAV, benchmark,
news, and sentiment evidence. Evidence readiness diagnostic only; not a
trading signal.

- `items`: list of `{fund_code, fund_name, recent_drawdown_pct,
  recent_rebound_pct, nav_confirmation, benchmark_confirmation,
  news_confirmation, sentiment_confirmation, right_side_confirmed,
  evidence_state, missing_reason, recommended_next_data}`
- `right_side_confirmed` is true only when nav is confirmed, benchmark is
  not negative, and news/sentiment are not negative
- When `right_side_confirmed` is false for action-oriented user goals,
  `right_side_unconfirmed` appears in `analysis_plan.blockers` or
  `analysis_plan.warnings`

### event_hype_failure_diagnostics

Deterministic event hype failure detection. Detects scenarios where an
expected positive catalyst/event failed to produce the expected price
reaction. Analysis-only; `suggested_analysis_action` is always
`watch | reduce_hype_weight | data_needed`.

- `items`: list of `{event_name, fund_code, fund_name,
  expected_positive_catalyst, post_event_return_pct,
  benchmark_post_event_return_pct, news_reaction, price_reaction,
  hype_failed, risk_level, evidence_state, missing_reason,
  suggested_analysis_action}`
- `hype_failed` is true when expected positive catalyst exists but price
  reaction is weak/negative and news does not offset
- High-risk hype failures add `event_hype_failed` to
  `analysis_plan.blockers` or `analysis_plan.warnings`

### cash_deployment_diagnostics

Deterministic cash deployment readiness assessment. Evaluates cash-like
allocation, buffer status, and risk budget. Does not recommend specific
buys; only provides readiness and missing data.

- `summary`: `{cash_like_value, cash_like_weight,
  estimated_deployable_cash, cash_buffer_status, deployment_readiness,
  risk_budget_status, notes}`
- `items`: list of `{bucket, value, weight, liquidity_hint}` per position
- `cash_buffer_status`: `low | adequate | high | unknown`
- `deployment_readiness`: `ready | partial | not_ready | unknown`
- When `deployment_readiness` is `not_ready`, `cash_deployment_not_ready`
  appears in `analysis_plan.warnings` or `analysis_plan.blockers`

### How to use analysis_plan

1. Call `fund_analysis` first with whatever data you have.
2. Read `analysis_plan.missing_inputs` and `evidence_gap_diagnostics`.
3. If `missing_recent_news` is true, call `news_research` with
   host-injected MCP responses.
4. If `missing_sentiment` is true and the user asks for action or timing,
   call `sentiment_analysis`.
5. If evidence is sufficient but no formal decision should be made yet,
   call `thesis_generation`.
6. **Only** call `decision_support` when
   `analysis_plan.decision_support_ready` is `true`.
7. If evidence is missing, stale, or insufficient, output WATCH or
   missing-evidence guidance rather than direct buy/sell advice.

**Do not hallucinate live data.** If news, sentiment, benchmark, or fee
data is missing, mark it as a gap and let the host fetch it.

## Outputs

### Artifacts produced

- `fund_analysis_report`
- `portfolio_summary`
- `position_summary`
- `exposure_summary`
- `risk_flags`
- `pnl_summary`
- `trade_budget`
- `short_term_trade_budget`
- `dca_review`
- `transaction_summary`
- `cost_basis_summary`
- `reconciliation`
- `suggested_rebalance_plan`
- `data_completeness` — host-provided data completeness score and grade (A-D)
- `analysis_coverage` — per-section availability summary
- `report_limitations` — user-facing limitations and caveats
- `report_sections` — deterministic host-displayable report sections
- `report_outline` — ordered section id/title/status summary
- `report_quality_gate` — publishability gate for professional reports
- `analysis_plan` — deterministic planning artifact: available/missing inputs,
  recommended skill sequence, decision_support readiness, blockers, warnings,
  next data to fetch
- `evidence_gap_diagnostics` — structured booleans for missing inputs with
  severity-coded details
- `position_contribution` — per-position PnL contribution analysis including
  portfolio weight, absolute/percentage PnL, contribution to total portfolio PnL,
  and risk contribution hints
- `profit_protection_diagnostics` — profit protection analysis for high-profit
  positions including profit level, principal recovery, free-carry estimate,
  trim/hold pressure, and suggested analysis action. Analysis-only; not a formal
  decision
- `redemption_fee_risk` — now includes `fee_items` with blocker/warning
  classification, `has_blocker`, and `has_warning` fields. Blockers prevent
  `decision_support` readiness
- `benchmark_divergence_diagnostics` — benchmark divergence analysis comparing
  fund return against benchmark return. Analysis-only; not a formal decision
- `right_side_confirmation_diagnostics` — right-side confirmation assessment
  for drawdown positions. Evidence readiness diagnostic only; not a trading
  signal
- `event_hype_failure_diagnostics` — event hype failure detection for expected
  positive catalysts with weak/negative post-event reaction. Analysis-only;
  not a formal decision
- `cash_deployment_diagnostics` — cash deployment readiness assessment
  including cash-like allocation, buffer status, and risk budget. Analysis-only;
  does not recommend specific buys
- `knowledge_graph_summary` — optional KnowledgeGraph-derived context layer
  summarizing entity relationships, sector/theme links, and cross-fund overlap
  patterns. Only emitted when holdings data supports KG construction. When
  holdings data is insufficient, this artifact is omitted (`enabled=false`).
  There is no requirement to have KG data for normal reports.
- `warnings`

Artifact availability depends on host-provided data.

`report_sections` are structured JSON, not prose generated by an LLM. Missing
benchmark, peer, manager, factor, fee, or redemption inputs become `PARTIAL` or
`MISSING` sections with limitations. Formal actions still require
`DecisionSupportSkill`. When `report_options.language` is `zh-CN`, the runtime
uses deterministic Chinese section titles and high-impact bullet templates for
portfolio value, data completeness, missing evidence, fee blockers/warnings,
decision readiness, next data to fetch, and uncertainty notes. Unknown language
values fall back to English.

### Evidence produced

The skill emits `HardEvidence` only. HardEvidence must have
`confidence_weight=1.0` and should anchor deterministic local calculations such
as allocation, concentration, NAV metrics, PnL, DCA review, market scenario
impact, and portfolio risk flags.

## Forbidden behavior

This skill must never:

- make direct network calls;
- import provider SDKs;
- call LLMs;
- fetch or invent fund, market, news, sentiment, or scenario data;
- generate formal `Decision` or `ExecutionLedger` artifacts;
- convert `suggested_rebalance_plan` into executable advice by itself;
- use `src.core.research_os` as a required path.

`fund_analysis` never emits `Decision` or `ExecutionLedger` under any
circumstances. This boundary is absolute regardless of input mode, data
availability, or pipeline stage.

## When to escalate to decision_support

Escalate only when the user asks for actionable trade advice or the host needs
formal decisions. The host should compile `SkillOutput.evidence_items` with
`compile_evidence_graph`, extract `suggested_rebalance_plan` if present, then
call `decision_support`. Include relevant `fund_analysis` artifacts such as
`analysis_plan`, `evidence_gap_diagnostics`, `redemption_fee_risk`,
`right_side_confirmation_diagnostics`, `event_hype_failure_diagnostics`, and
`cash_deployment_diagnostics` when they are available. Active decisions require
real evidence anchors and may be downgraded by `decision_support` when these
artifacts expose blockers.

## Minimal invocation example

```json
{
  "task_id": "task-1",
  "step_id": "fund-analysis-1",
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
          "shares": 12345.67,
          "target_weight": 0.12,
          "tags": ["healthcare", "active"]
        }
      ]
    },
    "fund_profiles": {
      "110011": {
        "fund_code": "110011",
        "name": "Example Fund",
        "fund_type": "active",
        "manager": "Manager",
        "benchmark": "Benchmark"
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
    },
    "report_options": {
      "language": "zh-CN",
      "detail_level": "professional"
    }
  },
  "kg_context": {},
  "required_mcp_capabilities": []
}
```

## OpenCode plugin adapter boundary

The OpenCode plugin adapter (`opencode.plugin.js`) provides metadata and
doc-reader functionality only. It lets the agent discover fund-agent skills
and read SKILL.md files. It does NOT launch Python, call the runtime bridge,
fetch live data, or manage MCP servers. Runtime execution requires host,
manual, Python subprocess, or other integration outside the OpenCode plugin.

## Agent-facing personal analysis package

For agent consumption, `bin/fund-agent-personal-run` produces a deterministic
evidence package including `agent_context.md`, `agent_context.json`,
`personal_health_report.json`, and `report.md`.

### First run (full pipeline)

**Real analysis** (recommended for actual portfolio review):

```bash
bin/fund-agent-personal-run --no-skip-akshare --skip-news
```

`--no-skip-akshare` enables live NAV provider for real valuations.
`--skip-news` remains on by default — news requires explicit user request.

**Offline / debugging** (deterministic, no live data):

```bash
bin/fund-agent-personal-run --skip-akshare --skip-news
```

If the NAV provider is unavailable, positions without NAV data will be
marked `cashflow_only` — no valuation will be fabricated. Do NOT treat
offline results as real analysis.

### Re-read existing run (skip pipeline)

```bash
bin/fund-agent-personal-run --agent-context-only --run-dir local_reports/<run_id>
```

### Agent reading order

1. `agent_context.json` — machine-readable status, scope, and constraints
2. `agent_context.md` — human-readable summary of the same data
3. `e2e_summary.json` — full pipeline summary (if deeper detail needed)
4. `personal_health_report.json` — data quality diagnostic and fix-it checklist
5. `report.md` — composed report (if user wants narrative)
6. Reconstructed portfolio / ledger — only if position-level detail is needed

### Agent output limits

Agents consuming this evidence package MUST NOT:

- Output formal `Decision` or `ExecutionLedger` objects
- Issue broker order execution instructions
- Auto-trade
- Treat `estimated` values as `confirmed` market values
- Treat partial valuation as complete portfolio market value
- Treat `cashflow_only` as current valuation
- Fabricate `fund_code`, NAV, or holdings
- Leak private paths or real transaction details

### Hard analysis constraints (v0.10.6)

These constraints are **absolute** — no data availability, user request, or
pipeline stage overrides them:

1. **Identity mismatch blocks valuation.** When a fund has
   `identity_verification_status=code_name_mismatch`, the agent MUST NOT
   output valuation, PnL, or yield for that fund. The position is
   `valuation_type=none` and `valuation_if_identity_mismatch` is in
   `unsafe_to_infer`. The agent should ask the user to verify
   `fund_identity_overrides` instead.

2. **Incomplete NAV/units/trade-date NAV → no market value, PnL, or yield.**
   When a position has `valuation_type=cashflow_only` or `nav_coverage_status`
   indicating missing trade-date NAV, the agent MUST NOT output market value,
   PnL (盈亏), or yield (收益率). These positions have `current_value=None` and
   `valuation_blocked_*` in `data_quality`. The agent should explain the gap
   and suggest providing NAV overrides or explicit units.

3. **Fee/redemption rate unknown → no confirmed PnL.** When
   `redemption_fee_unknown=True` or `fee_schedule_status=unavailable` for a
   position, the agent MUST NOT output confirmed PnL. It may state
   "estimated PnL before fees" with an explicit caveat. The agent should ask
   whether `fee_overrides` can be provided.

4. **Conversion/refund computability.** The agent MUST NOT assume all
   conversions/refunds are computable. Check `special_transaction_status`:
   - `computable`: units change is deterministic — may include in analysis
   - `estimated`: units change is approximate — include with caveat
   - `ambiguous` / `manual_review_required`: exclude from unit calculations,
     ask user to confirm

5. **15:00 cutoff for NAV lookup.** Transactions submitted before 15:00 on a
   trading day use T-date NAV; at or after 15:00 use T+1 NAV. The pipeline
   computes `effective_trade_date` from `submitted_at` and the 15:00 cutoff.
   The agent MUST NOT ignore this cutoff when interpreting trade-date NAV
   coverage or unit calculations.

6. **Agent report must not exceed evidence boundary.** The agent MUST NOT
   output analysis that is more certain than the underlying evidence allows.
   Specifically:
   - Do not state market value when `valuation_type` is not `estimated`
   - Do not state confirmed PnL when `redemption_fee_unknown=True`
   - Do not state yield/return when NAV coverage is partial
   - Do not state portfolio total value when some positions are blocked
   - Always qualify uncertain findings with the data quality flag or
     confidence level from the artifact

7. **Identity mismatch in unsafe_to_infer.** When `identity_mismatch` is in
   `reason_codes`, `valuation_if_identity_mismatch` appears in
   `unsafe_to_infer`. The agent MUST NOT infer valuation for mismatched funds
   even if the fund_code appears in the position list.

### Agent should prioritize

- Data quality explanation (overall_status, confidence_level, reason_codes)
- Missing data checklist (from `personal_health_report.fix_it_checklist`)
- Risk / exposure observations (with evidence citations and confidence qualifiers)
- User follow-up questions (from `agent_context.recommended_agent_questions`)

### Agent response structure

1. Data readiness — overall status, confidence, reason codes
2. What I can analyze now — safe-to-analyze scope
3. What is unsafe to infer — unsafe-to-infer scope
4. Key findings with evidence — each finding cites its artifact source
5. Missing data / fix-it checklist
6. Questions for user
7. Optional next run command

### Live data extension

When the user explicitly requests live data (news, real-time NAV):

- The agent should call the host's MCP provider
- Live data must be labeled separately from deterministic fund-agent evidence
- Live data does NOT upgrade `estimated` to `confirmed`
- Suggest re-running with `--no-skip-akshare` if live NAV should be integrated

### Prompt templates

See `docs/agent-integration/prompts/` for ready-to-use agent prompts:

- `analyze-agent-context.zh.md` — Chinese analysis prompt
- `analyze-agent-context.en.md` — English analysis prompt
- `follow-up-missing-data.zh.md` — Missing data follow-up prompt
- `live-provider-extension.zh.md` — Live data extension prompt

### Contract reference

- Design: `docs/design/agent-context-consumption-contract.md`
- Contract: `docs/contracts/agent-context-contract.v1.md`
- Schema version: `fund_agent_context.v1`

## Chinese personal fund example

A typical Chinese fund user scenario:

1. 用户持有半导体基金、创新药基金、债基和现金仓，询问是否减仓或加仓。
2. `fund_analysis` computes holdings, fees, risk, and evidence gaps.
3. `analysis_plan` shows `missing_recent_news` and `missing_benchmark_data`
   as blockers; `decision_support_ready` is `false`.
4. Agent calls `news_research` to get recent semiconductor and pharma news
   via host-injected MCP.
5. Agent calls `sentiment_analysis` if the user asked for action/timing.
6. With fresh evidence, `decision_support_ready` may become `true`.
7. Agent calls `decision_support` for a formal WATCH or TRIM decision.
8. Agent renders a Chinese report with risk warnings, evidence status,
   and cautious guidance.

If recent news or benchmark data is missing, output WATCH / missing-evidence
guidance rather than direct buy/sell advice.

## Report-writing guidance for host agents

Write the final report from artifacts and evidence, not from invented market
facts. For Chinese user requests, a concise Chinese report is appropriate:

- `结论先行`: summarize portfolio health, major risks, and data gaps.
- `组合结构`: explain cash ratio, weights, fund type, theme, and industry
  exposure before individual fund details.
- `风险提示`: name concentration, drawdown, DCA, short-term budget, and scenario
  warnings directly.
- `操作建议`: if no formal decision was requested, phrase as analysis or
  suggested next checks. If formal trade advice is requested, call
  `decision_support`.
- `证据附录`: include evidence IDs or artifact names used for each claim.
- `数据质量`: include `data_completeness` grade (A-D) and score; flag missing
  sections from `analysis_coverage`; surface `report_limitations` in the
  report preamble so readers understand what the report can and cannot say.
- `可选分析`: benchmark comparison, peer ranking, factor exposure, fee review,
  redemption constraints, and manager risk are available only when host provides
  the corresponding data. Do not fabricate missing optional analysis.

See `references/report-template.md` and `references/examples.md`.

## References

- `references/input-contract.md`
- `references/report-template.md`
- `references/risk-policy.md`
- `references/missing-data-policy.md`
- `references/dca-policy.md`
- `references/short-term-trade-policy.md`
- `references/market-scenario-policy.md`
- `references/examples.md`
