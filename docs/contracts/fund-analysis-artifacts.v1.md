# Fund Analysis Artifact Contract v1

**Version:** 1.0
**Contract ID:** `fund-analysis-artifacts.v1`
**Runtime ID:** `fund_analysis`
**Markdown skill slug:** `fund-analysis`
**Machine-readable contract:** `skillpack/artifact-contracts.yaml`

For the corresponding host-facing input contract, see
[`fund-analysis-input-contract.v1.md`](./fund-analysis-input-contract.v1.md)
and `skillpack/input-contracts.yaml`.

For the skill output contract (error objects, status values, warnings), see
[`skill-output-contract.v1.md`](./skill-output-contract.v1.md).

For decision_support formal decision contracts and fixtures, see
[`decision-support-contract.v1.md`](./decision-support-contract.v1.md),
[`skillpack/decision-contracts.yaml`](../../skillpack/decision-contracts.yaml),
and
[`examples/decision_support/README.md`](../../examples/decision_support/README.md).

This document defines the stable host-facing artifact contract for
`FundAnalysisSkill`.

## Scope

`fund_analysis` artifacts are deterministic outputs from host-supplied
portfolio, ledger, NAV, holdings, benchmark, peer, fee, manager, and scenario
data. The external host owns data fetching, MCP providers, credentials,
network access, retries, memory, orchestration, and final UX.

`fund_analysis` may produce analysis artifacts, warning and diagnostic
artifacts, deterministic `report_sections`, `report_outline`,
`report_quality_gate`, and suggested plans such as
`suggested_rebalance_plan` or `research_query_plan`.

`fund_analysis` MUST NOT produce formal `Decision` or `ExecutionLedger`
artifacts. Formal decisions belong only to `decision_support`.

Forbidden `fund_analysis` artifact keys are:

- `decision`
- `decisions`
- `execution_ledger`
- `execution_ledgers`

## Stability

Artifact keys listed in this contract are stable within contract v1. Adding
new optional artifact keys is backward-compatible. Removing or renaming an
existing contract key requires a contract version bump. Changing the semantics
of a required or core artifact requires a contract version bump.

Most artifacts are optional or conditional because they depend on host-supplied
data. Missing optional data must lead to warnings, limitations, `PARTIAL`
status, or omitted optional artifacts. `fund-agent` must not fabricate missing
benchmark comparisons, peer rankings, factor decompositions, fee analyses,
manager assessments, NAV history, ledger details, or scenario conclusions.

`report_sections`, `report_outline`, and `report_quality_gate` are expected for
normal structured portfolio/report runs, but minimal or baseline paths may
produce fewer artifacts.

Golden regression snapshots for representative `fund_analysis` fixture outputs
live under [`tests/golden/`](../../tests/golden/README.md) and can be
regenerated with
[`scripts/update_fund_analysis_golden.py`](../../scripts/update_fund_analysis_golden.py)
after intentional review.

## Artifact Categories

| Category | Meaning |
|---|---|
| `core_portfolio` | Portfolio snapshot, position, and source-of-truth outputs derived from host data. |
| `ledger_and_pnl` | Ledger-derived, cost-basis, cashflow, reconciliation, and PnL outputs. |
| `exposure_and_risk` | Allocation, exposure, risk flag, and scenario-impact outputs. |
| `planning_and_budget` | Deterministic budget, DCA review, research planning, and suggested rebalance outputs. |
| `optional_context` | Optional benchmark, peer, factor, fee, redemption, and manager context supplied by the host. |
| `report_output` | Deterministic structured report artifacts and Markdown-rendering inputs. |
| `diagnostics` | Warnings, data completeness, analysis coverage, limitations, and quality diagnostics. |

## Artifact Keys

`Top-level?` identifies whether the current v1 runtime places the key directly
under `SkillOutput.artifacts`. `trade_budget`, `transaction_summary`, and
`reconciliation` are current report payload fields under `fund_analysis_report`;
they are listed here because they are stable host-facing report fields, not
separate top-level artifacts in the current runtime.

| Artifact key | Category | Required? | Type summary | Top-level? | Produced when | Notes |
|---|---|---:|---|---|---|---|
| `fund_analysis_report` | `report_output` | No | object | Yes | Normal structured `fund_analysis` portfolio/report run. | Aggregated deterministic report payload. |
| `portfolio_summary` | `core_portfolio` | No | object | Yes | Portfolio snapshot or ledger-derived snapshot is available. | Portfolio-level value, weight, cash, and concentration summary. |
| `position_summary` | `core_portfolio` | No | object | Yes | Usable portfolio positions are available. | Position-level summary keyed by fund code. |
| `exposure_summary` | `exposure_and_risk` | No | object | Yes | Portfolio positions and holdings or tags are available. | Deterministic exposure rollup. |
| `risk_flags` | `exposure_and_risk` | No | list | Yes | Portfolio risk rules can run from host-supplied portfolio and constraints. | Includes portfolio, trading, and scenario risk flags. |
| `pnl_summary` | `ledger_and_pnl` | No | object or null | Yes | Cost and current value data are available for positions. | Derived from host-supplied cost, NAV, and ledger data. |
| `trade_budget` | `planning_and_budget` | No | object or null | No | Portfolio value and risk profile are available. | Current path: `fund_analysis_report.trade_budget`. |
| `short_term_trade_budget` | `planning_and_budget` | No | object or null | Yes | Transaction data is available. | Short-term budget from risk profile and transaction context. |
| `dca_plan_review` | `planning_and_budget` | No | object or null | Yes | Host supplies `dca_plans`. | Deterministic review of host-supplied DCA plans. |
| `transaction_summary` | `ledger_and_pnl` | No | object or null | No | Host supplies fund transaction data. | Current path: `fund_analysis_report.transaction_summary`. |
| `cost_basis_summary` | `ledger_and_pnl` | No | object or null | Yes | Host supplies transaction data. | Per-position cost basis summary. |
| `reconciliation` | `ledger_and_pnl` | No | object or null | No | Reconciliation can be computed from host-supplied portfolio and ledger data. | Current path: `fund_analysis_report.reconciliation`. |
| `suggested_rebalance_plan` | `planning_and_budget` | No | object or null | Yes | Target weights or rebalance constraints are available. | Analysis suggestion only; not a formal order or `Decision`. |
| `benchmark_summary` | `optional_context` | No | object | Yes | Host supplies benchmark or benchmark history data. | Optional benchmark comparison; omitted when data is missing. |
| `peer_summary` | `optional_context` | No | object | Yes | Host supplies peer group data. | Optional peer comparison; omitted when data is missing. |
| `factor_summary` | `optional_context` | No | object | Yes | Host supplies factor exposure data. | Optional factor/style summary. |
| `fee_summary` | `optional_context` | No | object | Yes | Host supplies fee schedule data. | Optional fee summary. |
| `redemption_summary` | `optional_context` | No | object | Yes | Host supplies redemption rule data. | Optional redemption and lockup summary. |
| `manager_summary` | `optional_context` | No | object | Yes | Host supplies manager profile data. | Optional manager profile summary. |
| `market_scenario_impact` | `exposure_and_risk` | No | object or null | Yes | Host supplies market scenario data. | Current runtime key for `scenario_summary`-style impact data. |
| `derived_portfolio_snapshot` | `core_portfolio` | No | object | Yes | Portfolio is derived from transactions plus `current_nav` and `as_of_date`. | Ledger-derived portfolio snapshot. |
| `ledger_cashflow_summary` | `ledger_and_pnl` | No | object or null | Yes | Portfolio is derived from transactions. | Cashflow, dividend, fee, and related ledger summary. |
| `source_of_truth` | `diagnostics` | No | string | Yes | Portfolio is derived from transactions. | Source indicator such as `derived_from_transactions`. |
| `ledger_quality_summary` | `diagnostics` | No | object | Yes | Portfolio is derived from transactions. | Ledger completeness and unresolved-event diagnostics. |
| `ledger_reconciliation_report` | `ledger_and_pnl` | No | object | Yes | Host supplies data that enables portfolio/ledger reconciliation. | Detailed reconciliation report. |
| `research_query_plan` | `planning_and_budget` | No | object | Yes | Host enables research planning context. | Deterministic plan for the host to execute externally. |
| `data_completeness` | `diagnostics` | No | object | Yes | Normal structured portfolio/report run. | Data completeness grade and score. |
| `analysis_coverage` | `diagnostics` | No | object | Yes | Normal structured portfolio/report run. | Per-section input coverage map. |
| `report_limitations` | `diagnostics` | No | list | Yes | Normal structured portfolio/report run. | User-facing caveats from missing or degraded data. |
| `report_sections` | `report_output` | No | list | Yes | Normal structured portfolio/report run. | Governed by `report-output-contract.v1.md`. |
| `report_outline` | `report_output` | No | list | Yes | Normal structured portfolio/report run. | Ordered outline derived from `report_sections`. |
| `report_quality_gate` | `report_output` | No | object | Yes | Normal structured portfolio/report run. | Deterministic publishability gate. |
| `warnings` | `diagnostics` | No | list | Yes | Warnings or limitations are detected. | Artifact-level warning list mirrored from `SkillOutput.warnings` when available. |
| `redemption_fee_risk` | `diagnostics` | No | object | No | Host supplies transactions, fee_schedules, and redemption_rules with short-holding fee rules. | Deterministic short-holding redemption fee risk diagnostic. |
| `overlap_diagnostics` | `diagnostics` | No | object | No | Host supplies holdings and fund_profiles for two or more funds. | Overlapping holdings, themes, and regions across funds. |
| `theme_overweight_diagnostics` | `diagnostics` | No | object | No | Host supplies fund_profiles.theme tags and risk_profile/constraints theme limits. | Theme concentration beyond configured limits. |
| `dca_drawdown_diagnostics` | `diagnostics` | No | object | No | Host supplies dca_plans and nav_history with recent drawdown. | DCA plan review under drawdown; diagnostic only. |
| `cash_budget_diagnostics` | `diagnostics` | No | object | No | Host supplies portfolio and risk_profile with liquidity/budget constraints. | Cash reserve and short-term budget diagnostic. |
| `professional_diagnostics` | `diagnostics` | No | object | No | Any professional diagnostic rule applies from host data. | Aggregated professional diagnostic results from local rules. |
| `analysis_plan` | `planning_and_budget` | No | object | Yes | Normal structured `fund_analysis` portfolio/report run. | Deterministic planning artifact: available/missing inputs, recommended skill sequence, decision_support readiness, blockers, and next data to fetch. |
| `evidence_gap_diagnostics` | `diagnostics` | No | object | Yes | Normal structured `fund_analysis` portfolio/report run. | Structured booleans for missing inputs with severity-coded details and recommended next data. |
| `position_contribution` | `ledger_and_pnl` | No | object | Yes | Portfolio positions with current_value are available. | Per-position PnL contribution analysis including portfolio weight, absolute/percentage PnL, and contribution to total portfolio PnL. |
| `profit_protection_diagnostics` | `diagnostics` | No | object | Yes | Portfolio positions with cost basis or transaction history are available. | Profit protection analysis for high-profit positions; analysis-only, not a formal decision. |

## Report Output

`report_sections`, `report_outline`, `report_quality_gate`, and deterministic
Markdown rendering are governed by
[`report-output-contract.v1.md`](./report-output-contract.v1.md).

Hosts may replace the final UX renderer, but they must preserve the
no-fabrication policy, section status semantics, and limitations display.
`--emit-report markdown` renders only deterministic `report_sections`; it does
not create formal decisions.

## Decision Boundary

`fund_analysis` artifacts may contain analysis summaries and suggested plans.
They are not formal investment decisions, executable orders, or execution
ledgers.

Only `decision_support` may produce formal `Decision` or `ExecutionLedger`
outputs. Active actions such as `BUY`, `SELL`, `INCREASE`, and `REDUCE`
require evidence anchors and must be generated by `DecisionSupportSkill`, not
`FundAnalysisSkill`.
