---
id: fund_analysis
name: fund-analysis
description: "Primary / default fund-agent skill. Produces HardEvidence (NAV metrics, holdings, portfolio review) from host-supplied portfolio / NAV / risk / constraints data. No network or provider calls."
runtime: src.skills_runtime.fund_analysis:FundAnalysisSkill
input_schema: src.schemas.skill:SkillInput
output_schema: src.schemas.skill:SkillOutput
required_mcp_capabilities: []
produced_evidence_type: HardEvidence
role: primary
---

# Fund Analysis

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
deterministic portfolio artifacts, risk flags, warnings, and `HardEvidence`.
This skill is the analytical layer for personal fund review. It is not a trade
decision engine and never emits formal `Decision` or `ExecutionLedger` objects.

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

See `references/input-contract.md` for the expanded payload contract.

## Missing-data degradation policy

Proceed with `PARTIAL` analysis when enough portfolio data exists to calculate
structure and risk. The skill computes a formal `data_completeness` score
(0.0-1.0) and grade (A-D) via `calculate_data_completeness()`. Grades C or D
trigger `PARTIAL` status automatically. Emit explicit `warnings` for missing
fund profiles, NAV history, holdings, transactions, DCA plans, or scenario
data. Do not fabricate missing data. If `portfolio.positions` is absent or
empty, return an `INVALID_INPUT` error. If only `related_entities` is
supplied, use the baseline HardEvidence compatibility path and warn that
structured portfolio analysis was not possible.

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
- `warnings`

Artifact availability depends on host-provided data.

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

## When to escalate to decision_support

Escalate only when the user asks for actionable trade advice or the host needs
formal decisions. The host should compile `SkillOutput.evidence_items` with
`compile_evidence_graph`, extract `suggested_rebalance_plan` if present, then
call `decision_support`. Active decisions require trade-specific evidence refs.

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
    }
  },
  "kg_context": {},
  "required_mcp_capabilities": []
}
```

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
